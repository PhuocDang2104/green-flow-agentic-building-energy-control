"""Receding-horizon predictive control over the telemetry spine.

This is an implementation scaffold with real data plumbing and deterministic
trajectory evaluation. It uses the MLflow/local surrogate provider when present
and falls back to conservative physics-inspired deltas when ML dependencies are
not installed.
"""

from __future__ import annotations

from functools import lru_cache
from datetime import datetime, timedelta, timezone
from typing import Iterable

import numpy as np

from ..config import get_settings
from ..datasets import active_dataset
from ..db import db_conn, fetch_all, fetch_one
from ..ml.model_registry import load_model
from ..replayclock import anchor
from .objective import ObjectiveWeights, score_objective
from .trajectory import action_step, trajectory

TZ = timezone(timedelta(hours=7))

SAFETY_ROOM_TYPES = {"technical_core"}
COMMON_ROOM_TYPES = {"circulation", "parking_shelter"}
SERVICE_ROOM_TYPES = {"service"}
CONTROLLABLE_ROOM_TYPES = {"workspace", "meeting_event", "amenity"}


def _local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def _parse_ts(value: str | None, building_id: str) -> datetime:
    if not value:
        return _local(anchor(building_id=building_id))
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _local(dt)


@lru_cache(maxsize=32)
def _demand_reference(building_id: str, scenario_id: str | None) -> dict:
    with db_conn() as conn:
        row = fetch_one(conn, """
            WITH demand AS (
              SELECT timestamp, sum(total_power_kw) AS kw
              FROM telemetry_zone_15m
              WHERE building_id = CAST(:building_id AS uuid)
                AND (CAST(:scenario_id AS text) IS NULL
                     OR scenario_id = CAST(:scenario_id AS text)
                     OR scenario_id IS NULL)
              GROUP BY timestamp
            )
            SELECT percentile_cont(0.90) WITHIN GROUP (ORDER BY kw) AS p90_kw,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY kw) AS p95_kw,
                   max(kw) AS max_kw
            FROM demand
        """, building_id=building_id, scenario_id=scenario_id)
    p90 = float((row or {}).get("p90_kw") or 0.0)
    p95 = float((row or {}).get("p95_kw") or 0.0)
    mx = float((row or {}).get("max_kw") or 0.0)
    return {
        "p90_kw": p90,
        "p95_kw": p95,
        "max_kw": mx,
        "peak_threshold_kw": max(p90, mx * 0.88) if mx else p90,
    }


def _room_policy_bucket(room_type: str | None) -> str:
    rt = (room_type or "unknown").strip().lower()
    if rt in SAFETY_ROOM_TYPES:
        return "safety_critical"
    if rt in COMMON_ROOM_TYPES:
        return "common_area"
    if rt in SERVICE_ROOM_TYPES:
        return "service_area"
    if rt in CONTROLLABLE_ROOM_TYPES:
        return "controllable"
    return "limited_control"


def _is_comfort_safe(zone: dict, *, max_temp_c: float = 25.8) -> bool:
    temp = float(zone.get("temperature_c") or 25.0)
    if temp >= max_temp_c:
        return False
    return (zone.get("comfort_risk") or "normal") != "high"


def build_semantic_state(building_id: str, issued_at: datetime | None = None,
                         *, scenario_id: str | None = None,
                         state_overrides: dict[str, dict] | None = None) -> dict:
    ds = active_dataset()
    issued_at = _local(issued_at or anchor(building_id=building_id))
    scenario = scenario_id or ds.scenario_id
    with db_conn() as conn:
        row = fetch_one(conn, """
            SELECT max(timestamp) AS ts
            FROM telemetry_zone_15m
            WHERE building_id = :b
              AND timestamp <= :ts
              AND (CAST(:scn AS text) IS NULL
                   OR scenario_id = CAST(:scn AS text)
                   OR scenario_id IS NULL)
        """, b=building_id, ts=issued_at, scn=scenario)
        ts = (row or {}).get("ts")
        if ts is None:
            row = fetch_one(conn, """
                SELECT max(timestamp) AS ts FROM telemetry_zone_15m WHERE building_id = :b
            """, b=building_id)
            ts = (row or {}).get("ts")
        if ts is None:
            raise ValueError("no telemetry available for predictive control")
        zones = fetch_all(conn, """
            SELECT z.id AS zone_id, z.entity_key, z.name, z.room_type,
                   COALESCE(z.area_m2, 50) AS area_m2,
                   COALESCE(z.volume_m3, COALESCE(z.area_m2, 50) * 3) AS volume_m3,
                   t.timestamp, t.occupancy_count, t.temperature_c, t.humidity_pct,
                   t.hvac_power_kw, t.lighting_power_kw, t.plug_power_kw,
                   t.total_power_kw, COALESCE(t.setpoint_c, 24) AS setpoint_c,
                   t.comfort_risk, t.peak_risk
            FROM telemetry_zone_15m t
            JOIN zones z ON z.id = t.zone_id
            WHERE t.building_id = :b
              AND t.timestamp = :ts
              AND (CAST(:scn AS text) IS NULL
                   OR t.scenario_id = CAST(:scn AS text)
                   OR t.scenario_id IS NULL)
            ORDER BY z.entity_key
        """, b=building_id, ts=ts, scn=scenario)
        weather = fetch_one(conn, """
            SELECT outdoor_temp_c, humidity_pct, wind_speed_mps, cloud_cover_pct,
                   solar_w_m2
            FROM weather_15m
            WHERE timestamp <= :ts
            ORDER BY timestamp DESC LIMIT 1
        """, ts=ts) or {}
        prev_ts_row = fetch_one(conn, """
            SELECT max(timestamp) AS ts
            FROM telemetry_zone_15m
            WHERE building_id = :b
              AND timestamp < :ts
              AND (CAST(:scn AS text) IS NULL
                   OR scenario_id = CAST(:scn AS text)
                   OR scenario_id IS NULL)
        """, b=building_id, ts=ts, scn=scenario)
        prev_occ = {}
        prev_available = (prev_ts_row or {}).get("ts") is not None
        if prev_available:
            prev_rows = fetch_all(conn, """
                SELECT z.entity_key, t.occupancy_count
                FROM telemetry_zone_15m t
                JOIN zones z ON z.id = t.zone_id
                WHERE t.building_id = :b
                  AND t.timestamp = :ts
                  AND (CAST(:scn AS text) IS NULL
                       OR t.scenario_id = CAST(:scn AS text)
                       OR t.scenario_id IS NULL)
            """, b=building_id, ts=prev_ts_row["ts"], scn=scenario)
            prev_occ = {str(r["entity_key"]): float(r.get("occupancy_count") or 0.0)
                        for r in prev_rows}
    overrides = state_overrides or {}
    for zone in zones:
        ov = overrides.get(zone["entity_key"])
        if ov:
            for key in ("temperature_c", "setpoint_c", "hvac_power_kw", "total_power_kw"):
                if key in ov and ov[key] is not None:
                    zone[key] = ov[key]
        occ = float(zone.get("occupancy_count") or 0.0)
        prev = float(prev_occ.get(str(zone["entity_key"]), 0.0))
        zone["previous_occupancy_count"] = prev
        zone["empty_streak_steps"] = (
            2 if prev_available and occ <= 0.1 and prev <= 0.1
            else 1 if occ <= 0.1
            else 0
        )
        zone["policy_bucket"] = _room_policy_bucket(zone.get("room_type"))
    loc = _local(ts)
    current_kw = sum(float(z.get("total_power_kw") or 0.0) for z in zones)
    demand_ref = _demand_reference(str(building_id), scenario)
    return {
        "metadata": {
            **ds.to_metadata(),
            "building_id": building_id,
            "scenario_id": scenario,
            "issued_at": loc.isoformat(),
            "zone_count": len(zones),
            "current_demand_kw": round(current_kw, 3),
            "demand_reference": demand_ref,
            "peak_threshold_kw": round(demand_ref.get("peak_threshold_kw") or 0.0, 3),
        },
        "timestamp": loc,
        "weather": {
            "outdoor_temp_c": float(weather.get("outdoor_temp_c") or 30.0),
            "outdoor_rh_pct": float(weather.get("humidity_pct") or 70.0),
            "wind_speed_m_s": float(weather.get("wind_speed_mps") or 2.0),
            "cloud_cover_pct": float(weather.get("cloud_cover_pct") or 40.0),
            "ghi": float(weather.get("solar_w_m2") or 0.0),
        },
        "zones": zones,
    }


def _weather_for_step(state: dict, step: int) -> dict:
    # Phase-1 implementation uses persisted current weather as the exogenous
    # baseline. The data model already has 30-min weather; replay can refine this
    # by rebuilding state at each timestep.
    return state["weather"]


def _rows_for_step(state: dict, step: int, setpoint_delta: dict[str, float]) -> list[dict]:
    ts = state["timestamp"] + timedelta(minutes=state["metadata"]["timestep_minutes"] * step)
    rows = []
    weather = _weather_for_step(state, step)
    for z in state["zones"]:
        base_sp = float(z.get("setpoint_c") or 24.0)
        sp = min(27.5, max(18.0, base_sp + setpoint_delta.get(z["entity_key"], 0.0)))
        rows.append({
            "zone_key": z["entity_key"],
            "room_type": z.get("room_type"),
            "policy_bucket": z.get("policy_bucket") or _room_policy_bucket(z.get("room_type")),
            "timestamp": ts,
            "hour": ts.hour,
            "dow": ts.weekday(),
            "month": ts.month,
            "office_hours_flag": 1 if (7 <= ts.hour < 19 and ts.weekday() < 5) else 0,
            "cooling_setpoint_c": sp,
            "area_m2": float(z.get("area_m2") or 50.0),
            "volume_m3": float(z.get("volume_m3") or (float(z.get("area_m2") or 50.0) * 3)),
            "ceiling_height_m": 3.0,
            "outdoor_temp_c": weather["outdoor_temp_c"],
            "outdoor_rh_pct": weather["outdoor_rh_pct"],
            "ghi": weather["ghi"],
            "wind": weather["wind_speed_m_s"],
            "cloud": weather["cloud_cover_pct"],
            "baseline_total_kw": float(z.get("total_power_kw") or 0.0),
            "baseline_hvac_kw": float(z.get("hvac_power_kw") or 0.0),
            "baseline_lighting_kw": float(z.get("lighting_power_kw") or 0.0),
            "baseline_temp_c": float(z.get("temperature_c") or 25.0),
            "occupancy_count": float(z.get("occupancy_count") or 0.0),
            "empty_streak_steps": int(z.get("empty_streak_steps") or 0),
            "base_setpoint_c": base_sp,
        })
    return rows


def _frame(rows: list[dict], features: list[str]):
    import pandas as pd
    h = np.array([r["hour"] for r in rows], dtype=float)
    dow = np.array([r["dow"] for r in rows], dtype=float)
    mon = np.array([r["month"] for r in rows], dtype=float)
    full = {
        "outdoor_temp_c": [r["outdoor_temp_c"] for r in rows],
        "outdoor_rh_pct": [r["outdoor_rh_pct"] for r in rows],
        "global_horizontal_radiation_wh_m2": [r["ghi"] for r in rows],
        "wind_speed_m_s": [r["wind"] for r in rows],
        "cloud_cover_pct": [r["cloud"] for r in rows],
        "hour_sin": np.sin(2 * np.pi * h / 24),
        "hour_cos": np.cos(2 * np.pi * h / 24),
        "dayofweek_sin": np.sin(2 * np.pi * dow / 7),
        "dayofweek_cos": np.cos(2 * np.pi * dow / 7),
        "month_sin": np.sin(2 * np.pi * mon / 12),
        "month_cos": np.cos(2 * np.pi * mon / 12),
        "office_hours_flag": [r["office_hours_flag"] for r in rows],
        "cooling_setpoint_c": [r["cooling_setpoint_c"] for r in rows],
        "area_m2": [r["area_m2"] for r in rows],
        "volume_m3": [r["volume_m3"] for r in rows],
        "ceiling_height_m": [r["ceiling_height_m"] for r in rows],
        "area_m2_final": [r["area_m2"] for r in rows],
        "volume_m3_final": [r["volume_m3"] for r in rows],
        "height_m_final": [r["ceiling_height_m"] for r in rows],
    }
    return pd.DataFrame({k: full[k] for k in features})


def _predict_total_kw(rows: list[dict]) -> tuple[np.ndarray, dict]:
    loaded = load_model("zone")
    if loaded is not None and loaded.model is not None and loaded.features:
        try:
            rows_25 = [{**row, "cooling_setpoint_c": 25.0} for row in rows]
            rows_26 = [{**row, "cooling_setpoint_c": 26.0} for row in rows]
            pred_25 = np.clip(loaded.model.predict(_frame(rows_25, loaded.features)), 0, None)
            pred_26 = np.clip(loaded.model.predict(_frame(rows_26, loaded.features)), 0, None)
            elasticity = np.clip(pred_25 - pred_26, 0, None)
            delta = np.array([
                row["cooling_setpoint_c"] - row["base_setpoint_c"] for row in rows
            ])
            measured = np.array([row["baseline_total_kw"] for row in rows])
            pred = np.clip(measured - elasticity * delta, 0, None)
            return pred.astype(float), loaded.metadata()
        except Exception as exc:  # noqa: BLE001
            meta = loaded.metadata()
            meta["prediction_error"] = repr(exc)[:160]
    else:
        meta = {"source": "heuristic", "registered_model": "greenflow_surrogate_zone"}
    # Conservative fallback: raising setpoint saves about 6% HVAC per degree.
    out = []
    for r in rows:
        delta = r["cooling_setpoint_c"] - r["base_setpoint_c"]
        hvac = r["baseline_hvac_kw"] * max(0.0, 1.0 - 0.06 * max(delta, 0.0))
        if delta < 0:
            hvac = r["baseline_hvac_kw"] * (1.0 + 0.04 * abs(delta))
        total = max(0.0, r["baseline_total_kw"] - r["baseline_hvac_kw"] + hvac)
        out.append(total)
    return np.array(out, dtype=float), meta


def _zones_by_condition(state: dict) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {
        "empty_controllable": [],
        "low_controllable": [],
        "occupied_controllable": [],
        "common_area": [],
        "service_area": [],
        "limited_control": [],
        "safe_empty": [],
        "safe_low": [],
        "safe_occupied": [],
        "high_load": [],
    }
    ranked_for_load = []
    for z in state["zones"]:
        key = str(z["entity_key"])
        bucket = z.get("policy_bucket") or _room_policy_bucket(z.get("room_type"))
        if bucket == "safety_critical":
            continue
        occ = float(z.get("occupancy_count") or 0.0)
        empty = occ <= 0.1 and int(z.get("empty_streak_steps") or 0) >= 2
        low = not empty and occ <= 2.0
        safe = _is_comfort_safe(z)
        if bucket == "common_area":
            groups["common_area"].append(key)
        elif bucket == "service_area":
            groups["service_area"].append(key)
        elif bucket == "controllable":
            if empty:
                groups["empty_controllable"].append(key)
            elif low:
                groups["low_controllable"].append(key)
            else:
                groups["occupied_controllable"].append(key)
        else:
            groups["limited_control"].append(key)
        if safe:
            if empty:
                groups["safe_empty"].append(key)
            elif low:
                groups["safe_low"].append(key)
            else:
                groups["safe_occupied"].append(key)
        load = float(z.get("total_power_kw") or 0.0)
        if safe and load > 0.05:
            ranked_for_load.append((load, key))
    groups["high_load"] = [key for _, key in sorted(ranked_for_load, reverse=True)[:40]]
    return groups


def _is_peak_context(state: dict, ts: datetime) -> bool:
    ref = state["metadata"].get("demand_reference") or {}
    current_kw = float(state["metadata"].get("current_demand_kw") or 0.0)
    p90 = float(ref.get("p90_kw") or 0.0)
    p95 = float(ref.get("p95_kw") or 0.0)
    threshold = float(state["metadata"].get("peak_threshold_kw") or ref.get("peak_threshold_kw") or 0.0)
    if threshold and current_kw >= threshold * 0.90:
        return True
    if p95 and current_kw >= p95 * 0.88:
        return True
    if 13 <= ts.hour < 17 and p90 and current_kw >= p90 * 0.70:
        return True
    return False


def _is_pre_peak_context(state: dict, ts: datetime) -> bool:
    ref = state["metadata"].get("demand_reference") or {}
    current_kw = float(state["metadata"].get("current_demand_kw") or 0.0)
    p90 = float(ref.get("p90_kw") or 0.0)
    return 10 <= ts.hour < 13 and (not p90 or current_kw >= p90 * 0.55)


def _add_lighting_actions(actions: list[dict], *, step: int, ts: datetime, step_min: int,
                          groups: dict[str, list[str]], factors: dict[str, float],
                          action_type: str, reason: str, trigger: str) -> None:
    labels = {
        "empty_controllable": "empty controllable zones",
        "low_controllable": "low-occupancy controllable zones",
        "occupied_controllable": "occupied controllable zones",
        "common_area": "common/circulation zones",
        "service_area": "service zones",
        "limited_control": "limited-control zones",
    }
    for group, factor in factors.items():
        targets = groups.get(group) or []
        if not targets or factor >= 1.0:
            continue
        actions.append(action_step(
            step=step, start=ts, step_minutes=step_min,
            action_type=action_type, target_zone_keys=targets,
            lighting_factor=factor,
            reason=f"{reason}: {labels.get(group, group)}",
            metadata={"policy_group": group, "trigger": trigger},
        ))


def _add_setback_action(actions: list[dict], *, step: int, ts: datetime, step_min: int,
                        action_type: str, targets: list[str], delta: float,
                        reason: str, trigger: str, policy_group: str) -> None:
    if not targets or abs(delta) < 0.001:
        return
    actions.append(action_step(
        step=step, start=ts, step_minutes=step_min,
        action_type=action_type, target_zone_keys=targets,
        setpoint_delta_c=delta,
        reason=reason,
        metadata={"policy_group": policy_group, "trigger": trigger},
    ))


def generate_candidate_trajectories(state: dict, *, horizon_steps: int, top_k: int) -> list[dict]:
    step_min = int(state["metadata"]["timestep_minutes"])
    start = state["timestamp"]
    groups = _zones_by_condition(state)
    candidates = [
        trajectory("baseline_hold", start, horizon_steps, step_min, [], "baseline"),
    ]

    actions = []
    for step in range(1, horizon_steps + 1):
        ts = start + timedelta(minutes=step_min * step)
        if 6 <= ts.hour < 22:
            _add_lighting_actions(
                actions, step=step, ts=ts, step_min=step_min, groups=groups,
                factors={
                    "empty_controllable": 0.22,
                    "low_controllable": 0.55,
                    "occupied_controllable": 0.88,
                    "common_area": 0.82,
                    "service_area": 0.45,
                    "limited_control": 0.76,
                },
                action_type="occupancy_based_lighting_dim",
                reason="Dim lighting according to occupancy and space policy",
                trigger="occupancy_policy",
            )
            _add_setback_action(
                actions, step=step, ts=ts, step_min=step_min,
                action_type="comfort_safe_hvac_setback",
                targets=groups["safe_empty"][:160],
                delta=1.25,
                reason="Raise cooling setpoint in empty comfort-safe zones",
                trigger="occupancy_policy",
                policy_group="safe_empty",
            )
            _add_setback_action(
                actions, step=step, ts=ts, step_min=step_min,
                action_type="comfort_safe_hvac_setback",
                targets=groups["safe_low"][:160],
                delta=0.65,
                reason="Raise cooling setpoint in low-occupancy comfort-safe zones",
                trigger="occupancy_policy",
                policy_group="safe_low",
            )
            _add_setback_action(
                actions, step=step, ts=ts, step_min=step_min,
                action_type="comfort_safe_hvac_setback",
                targets=groups["safe_occupied"][:80],
                delta=0.25,
                reason="Apply a mild occupied-zone setback only where comfort margin is safe",
                trigger="occupancy_policy",
                policy_group="safe_occupied",
            )
    candidates.append(trajectory("occupancy_aware_efficiency", start, horizon_steps, step_min,
                                 actions, "policy_aware_energy"))

    actions = []
    for step in range(1, horizon_steps + 1):
        ts = start + timedelta(minutes=step_min * step)
        if _is_peak_context(state, ts):
            _add_lighting_actions(
                actions, step=step, ts=ts, step_min=step_min, groups=groups,
                factors={
                    "empty_controllable": 0.15,
                    "low_controllable": 0.43,
                    "occupied_controllable": 0.85,
                    "common_area": 0.78,
                    "service_area": 0.38,
                    "limited_control": 0.70,
                },
                action_type="peak_aware_lighting_trim",
                reason="Trim lighting during predicted demand stress",
                trigger="forecast_peak",
            )
            _add_setback_action(
                actions, step=step, ts=ts, step_min=step_min,
                action_type="comfort_safe_hvac_setback",
                targets=groups["safe_empty"][:180],
                delta=1.5,
                reason="Use stronger empty-zone cooling setback during demand stress",
                trigger="forecast_peak",
                policy_group="safe_empty",
            )
            _add_setback_action(
                actions, step=step, ts=ts, step_min=step_min,
                action_type="comfort_safe_hvac_setback",
                targets=groups["safe_low"][:180],
                delta=1.0,
                reason="Use low-occupancy cooling setback during demand stress",
                trigger="forecast_peak",
                policy_group="safe_low",
            )
            _add_setback_action(
                actions, step=step, ts=ts, step_min=step_min,
                action_type="comfort_safe_hvac_setback",
                targets=groups["safe_occupied"][:120],
                delta=0.5,
                reason="Use mild occupied-zone cooling setback under peak stress",
                trigger="forecast_peak",
                policy_group="safe_occupied",
            )
            _add_setback_action(
                actions, step=step, ts=ts, step_min=step_min,
                action_type="electrical_stress_reduction_proxy",
                targets=groups["high_load"][:40],
                delta=0.25,
                reason="Reduce high-load zone stress while board ratings are unavailable",
                trigger="forecast_peak",
                policy_group="high_load_proxy",
            )
    candidates.append(trajectory("peak_aware_demand_response", start, horizon_steps, step_min,
                                 actions, "peak_shaving"))

    actions = []
    for step in range(1, horizon_steps + 1):
        ts = start + timedelta(minutes=step_min * step)
        if groups["safe_empty"] or groups["safe_low"] or groups["safe_occupied"]:
            _add_setback_action(
                actions, step=step, ts=ts, step_min=step_min,
                action_type="comfort_safe_hvac_setback",
                targets=groups["safe_empty"][:160],
                delta=1.0,
                reason="Conservative empty-zone HVAC setback",
                trigger="comfort_first",
                policy_group="safe_empty",
            )
            _add_setback_action(
                actions, step=step, ts=ts, step_min=step_min,
                action_type="comfort_safe_hvac_setback",
                targets=groups["safe_low"][:120],
                delta=0.5,
                reason="Conservative low-occupancy HVAC setback",
                trigger="comfort_first",
                policy_group="safe_low",
            )
            _add_setback_action(
                actions, step=step, ts=ts, step_min=step_min,
                action_type="comfort_safe_hvac_setback",
                targets=groups["safe_occupied"][:60],
                delta=0.25,
                reason="Very mild occupied-zone HVAC setback",
                trigger="comfort_first",
                policy_group="safe_occupied",
            )
    candidates.append(trajectory("comfort_safe_hvac_only", start, horizon_steps, step_min,
                                 actions, "comfort_first"))

    actions = []
    for step in range(1, horizon_steps + 1):
        ts = start + timedelta(minutes=step_min * step)
        if _is_pre_peak_context(state, ts):
            _add_setback_action(
                actions, step=step, ts=ts, step_min=step_min,
                action_type="pre_peak_precool",
                targets=(groups["safe_occupied"] + groups["safe_low"])[:120],
                delta=-0.25,
                reason="Pre-cool a small comfort-safe subset before the forecast peak",
                trigger="pre_peak_shift",
                policy_group="safe_pre_peak",
            )
        elif _is_peak_context(state, ts):
            _add_lighting_actions(
                actions, step=step, ts=ts, step_min=step_min, groups=groups,
                factors={
                    "empty_controllable": 0.20,
                    "low_controllable": 0.48,
                    "occupied_controllable": 0.86,
                    "common_area": 0.80,
                    "service_area": 0.42,
                    "limited_control": 0.74,
                },
                action_type="peak_aware_lighting_trim",
                reason="Follow pre-peak shift with moderate demand response",
                trigger="pre_peak_shift",
            )
            _add_setback_action(
                actions, step=step, ts=ts, step_min=step_min,
                action_type="comfort_safe_hvac_setback",
                targets=(groups["safe_empty"] + groups["safe_low"] + groups["safe_occupied"])[:180],
                delta=0.75,
                reason="Release pre-cooling with comfort-safe peak setback",
                trigger="pre_peak_shift",
                policy_group="safe_peak_release",
            )
    candidates.append(trajectory("pre_peak_demand_shift", start, horizon_steps, step_min,
                                 actions, "load_shift"))
    return candidates


def _mods_for_step(candidate: dict, step: int) -> dict[str, dict]:
    mods: dict[str, dict] = {}
    for a in candidate.get("actions", []):
        if int(a.get("step") or 0) != step:
            continue
        for key in a.get("target_zone_keys") or []:
            rec = mods.setdefault(key, {
                "setpoint_delta_c": 0.0,
                "lighting_factor": 1.0,
                "action_types": set(),
            })
            rec["setpoint_delta_c"] += float(a.get("setpoint_delta_c") or 0.0)
            if a.get("lighting_factor") is not None:
                rec["lighting_factor"] = min(rec["lighting_factor"], float(a["lighting_factor"]))
            rec["action_types"].add(str(a.get("action_type") or "unknown"))
    return mods


def evaluate_trajectory(state: dict, candidate: dict,
                        *, weights: ObjectiveWeights | None = None) -> dict:
    step_h = int(state["metadata"]["timestep_minutes"]) / 60.0
    baseline_energy = optimized_energy = comfort_min = 0.0
    baseline_comfort_min = ai_added_comfort_min = 0.0
    lighting_saving_kwh = hvac_saving_kwh = 0.0
    policy_violation_count = 0
    time_above_threshold_min = 0.0
    peak_kw = ramp_kw = 0.0
    prev_total = None
    action_changes = 0
    first_step_zone_states: list[dict] = []
    step_predictions = []
    model_meta = None
    peak_threshold_kw = float(state["metadata"].get("peak_threshold_kw") or 0.0)
    for step in range(1, int(candidate["horizon_steps"]) + 1):
        mods = _mods_for_step(candidate, step)
        action_changes += sum(1 for a in candidate.get("actions", [])
                              if int(a.get("step") or 0) == step)
        deltas = {k: v["setpoint_delta_c"] for k, v in mods.items()}
        base_rows = _rows_for_step(state, step, {})
        rows = _rows_for_step(state, step, deltas)
        pred_base_kw, model_meta = _predict_total_kw(base_rows)
        pred_action_kw, model_meta = _predict_total_kw(rows)
        base_kw = np.array([r["baseline_total_kw"] for r in rows], dtype=float)

        # Calibrate the surrogate to the measured E+ telemetry at this timestep:
        # use the model only for the action delta, not for absolute load. This
        # prevents replay baseline drift and rejects zone-level actions that the
        # surrogate predicts would increase energy.
        reduction_kw = np.maximum(pred_base_kw - pred_action_kw, 0.0)
        opt_kw = np.maximum(0.0, base_kw - reduction_kw)
        step_hvac_saving_kw = float(reduction_kw.sum())

        # Lighting factor is an explicit schedule modifier not learned by the
        # setpoint surrogate; apply it as a transparent delta against measured
        # lighting load.
        step_lighting_saving_kw = 0.0
        step_policy_violations = 0
        for i, r in enumerate(rows):
            mod = mods.get(r["zone_key"], {})
            factor = float(mod.get("lighting_factor", 1.0))
            delta = float(mod.get("setpoint_delta_c", 0.0))
            action_types = mod.get("action_types") or set()
            if "pre_peak_precool" in action_types and delta < 0:
                extra_kw = r["baseline_hvac_kw"] * min(0.10, 0.05 * abs(delta))
                opt_kw[i] = opt_kw[i] + extra_kw
                step_hvac_saving_kw -= extra_kw
            if factor < 1.0:
                lighting_delta = r["baseline_lighting_kw"] * (1.0 - factor)
                opt_kw[i] = max(0.0, opt_kw[i] - lighting_delta)
                step_lighting_saving_kw += lighting_delta
            bucket = r["policy_bucket"]
            occ = float(r["occupancy_count"] or 0.0)
            if bucket == "safety_critical" and (factor < 1.0 or abs(delta) > 0.001):
                step_policy_violations += 1
            if bucket == "common_area" and factor < 0.78:
                step_policy_violations += 1
            if bucket == "service_area" and factor < 0.38:
                step_policy_violations += 1
            if bucket == "limited_control" and factor < 0.70:
                step_policy_violations += 1
            if bucket == "controllable" and occ >= 0.5:
                min_factor = 0.43 if occ <= 2.0 else 0.85
                if factor < min_factor:
                    step_policy_violations += 1
        if not any("pre_peak_precool" in (m.get("action_types") or set()) for m in mods.values()):
            opt_kw = np.minimum(opt_kw, base_kw)
        step_total = float(opt_kw.sum())
        baseline_total = float(base_kw.sum())
        baseline_energy += baseline_total * step_h
        optimized_energy += step_total * step_h
        lighting_saving_kwh += step_lighting_saving_kw * step_h
        hvac_saving_kwh += step_hvac_saving_kw * step_h
        peak_kw = max(peak_kw, step_total)
        if peak_threshold_kw and step_total > peak_threshold_kw:
            time_above_threshold_min += state["metadata"]["timestep_minutes"]
        if prev_total is not None:
            ramp_kw = max(ramp_kw, abs(step_total - prev_total))
        prev_total = step_total
        step_comfort = 0.0
        step_baseline_comfort = 0.0
        zone_states = []
        for i, r in enumerate(rows):
            delta = mods.get(r["zone_key"], {}).get("setpoint_delta_c", 0.0)
            temp = r["baseline_temp_c"] + 0.4 * delta
            baseline_violated = r["occupancy_count"] >= 0.5 and r["baseline_temp_c"] > 26.5
            ai_violated = r["occupancy_count"] >= 0.5 and temp > 26.5
            if baseline_violated:
                step_baseline_comfort += state["metadata"]["timestep_minutes"]
            if ai_violated:
                step_comfort += state["metadata"]["timestep_minutes"]
            zone_states.append({
                "zone_key": r["zone_key"],
                "total_power_kw": round(float(opt_kw[i]), 4),
                "hvac_power_kw": round(max(0.0, r["baseline_hvac_kw"] * (float(opt_kw[i]) / max(r["baseline_total_kw"], 0.001))), 4),
                "setpoint_c": round(r["cooling_setpoint_c"], 3),
                "temperature_c": round(temp, 3),
            })
        comfort_min += step_comfort
        baseline_comfort_min += step_baseline_comfort
        ai_added_comfort_min += max(0.0, step_comfort - step_baseline_comfort)
        policy_violation_count += step_policy_violations
        if step == 1:
            first_step_zone_states = zone_states
        step_predictions.append({
            "step": step,
            "baseline_kw": round(baseline_total, 3),
            "optimized_kw": round(step_total, 3),
            "baseline_comfort_violation_min": round(step_baseline_comfort, 1),
            "comfort_violation_min": round(step_comfort, 1),
            "ai_added_comfort_violation_min": round(max(0.0, step_comfort - step_baseline_comfort), 1),
            "lighting_saving_kwh": round(step_lighting_saving_kw * step_h, 4),
            "hvac_saving_kwh": round(step_hvac_saving_kw * step_h, 4),
            "policy_violation_count": step_policy_violations,
            "peak_threshold_kw": round(peak_threshold_kw, 3) if peak_threshold_kw else None,
        })
    policy_risk = float(policy_violation_count)
    objective = score_objective(
        energy_kwh=optimized_energy,
        peak_kw=peak_kw,
        comfort_minutes=comfort_min,
        ramp_kw=ramp_kw,
        action_changes=action_changes,
        policy_risk=policy_risk,
        peak_threshold_kw=peak_threshold_kw or None,
        time_above_threshold_min=time_above_threshold_min,
        weights=weights,
    )
    out = dict(candidate)
    out.update({
        "predicted": {
            "baseline_energy_kwh": round(baseline_energy, 3),
            "energy_kwh": round(optimized_energy, 3),
            "saving_kwh": round(baseline_energy - optimized_energy, 3),
            "peak_kw": round(peak_kw, 3),
            "peak_threshold_kw": round(peak_threshold_kw, 3) if peak_threshold_kw else None,
            "time_above_threshold_min": round(time_above_threshold_min, 1),
            "baseline_comfort_violation_min": round(baseline_comfort_min, 1),
            "comfort_violation_min": round(comfort_min, 1),
            "ai_added_comfort_violation_min": round(ai_added_comfort_min, 1),
            "lighting_saving_kwh": round(lighting_saving_kwh, 3),
            "hvac_saving_kwh": round(hvac_saving_kwh, 3),
            "policy_violation_count": policy_violation_count,
            "ramp_kw": round(ramp_kw, 3),
        },
        "objective": objective,
        "model": model_meta or {"source": "heuristic"},
        "step_predictions": step_predictions,
        "_first_step_zone_states": first_step_zone_states,
    })
    return out


def select_best(scored: Iterable[dict]) -> dict:
    return min(scored, key=lambda c: c.get("objective", {}).get("score", float("inf")))


def run_predictive_control(building_id: str, *, timestamp: str | None = None,
                           scenario_id: str | None = None,
                           horizon_steps: int | None = None,
                           top_k: int | None = None,
                           state_overrides: dict[str, dict] | None = None) -> dict:
    s = get_settings()
    issued_at = _parse_ts(timestamp, building_id)
    horizon = int(horizon_steps or s.greenflow_control_horizon_steps)
    top = int(top_k or s.greenflow_control_top_k)
    state = build_semantic_state(building_id, issued_at, scenario_id=scenario_id,
                                 state_overrides=state_overrides)
    candidates = generate_candidate_trajectories(state, horizon_steps=horizon, top_k=top)
    scored_all = [evaluate_trajectory(state, c) for c in candidates]
    scored = sorted(scored_all, key=lambda c: c.get("objective", {}).get("score", float("inf")))
    best = select_best(scored)
    execute_actions = [a for a in best.get("actions", []) if int(a.get("step") or 0) == 1]
    execute_action = execute_actions[0] if execute_actions else None
    return {
        "metadata": {
            **state["metadata"],
            "control_mode": "predictive_receding_horizon",
            "horizon_steps": horizon,
            "top_k": top,
            "objective_version": "v2_policy_aware",
        },
        "selected": {k: v for k, v in best.items() if not k.startswith("_")},
        "execute_action": execute_action,
        "execute_actions": execute_actions,
        "candidates": [{k: v for k, v in c.items() if not k.startswith("_")}
                       for c in scored[:max(1, top)]],
        "_first_step_zone_states": best.get("_first_step_zone_states", []),
    }

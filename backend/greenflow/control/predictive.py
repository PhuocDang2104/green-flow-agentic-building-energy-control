"""Receding-horizon predictive control over the telemetry spine.

This is an implementation scaffold with real data plumbing and deterministic
trajectory evaluation. It uses the MLflow/local surrogate provider when present
and falls back to conservative physics-inspired deltas when ML dependencies are
not installed.
"""

from __future__ import annotations

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


def _local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def _parse_ts(value: str | None, building_id: str) -> datetime:
    if not value:
        return _local(anchor(building_id=building_id))
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _local(dt)


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
    overrides = state_overrides or {}
    for zone in zones:
        ov = overrides.get(zone["entity_key"])
        if ov:
            for key in ("temperature_c", "setpoint_c", "hvac_power_kw", "total_power_kw"):
                if key in ov and ov[key] is not None:
                    zone[key] = ov[key]
    loc = _local(ts)
    return {
        "metadata": {
            **ds.to_metadata(),
            "building_id": building_id,
            "scenario_id": scenario,
            "issued_at": loc.isoformat(),
            "zone_count": len(zones),
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
        sp = float(z.get("setpoint_c") or 24.0) + setpoint_delta.get(z["entity_key"], 0.0)
        rows.append({
            "zone_key": z["entity_key"],
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
            "base_setpoint_c": float(z.get("setpoint_c") or 24.0),
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
    }
    return pd.DataFrame({k: full[k] for k in features})


def _predict_total_kw(rows: list[dict]) -> tuple[np.ndarray, dict]:
    loaded = load_model("zone")
    if loaded is not None and loaded.model is not None and loaded.features:
        try:
            pred = np.clip(loaded.model.predict(_frame(rows, loaded.features)), 0, None)
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
    zones = state["zones"]
    safe, empty, large = [], [], []
    for z in zones:
        key = z["entity_key"]
        temp = float(z.get("temperature_c") or 25.0)
        occ = float(z.get("occupancy_count") or 0.0)
        if temp < 25.8 and (z.get("comfort_risk") or "normal") != "high":
            safe.append(key)
        if occ <= 0.1:
            empty.append(key)
    large = [z["entity_key"] for z in sorted(zones, key=lambda r: -(float(r.get("area_m2") or 0)))[:20]]
    return {"safe": safe, "empty": empty, "large": large}


def generate_candidate_trajectories(state: dict, *, horizon_steps: int, top_k: int) -> list[dict]:
    step_min = int(state["metadata"]["timestep_minutes"])
    start = state["timestamp"]
    groups = _zones_by_condition(state)
    safe = groups["safe"][:120]
    empty = groups["empty"][:120]
    large = groups["large"]
    candidates = [
        trajectory("baseline_hold", start, horizon_steps, step_min, [], "baseline"),
    ]

    actions = []
    for step in range(1, horizon_steps + 1):
        ts = start + timedelta(minutes=step_min * step)
        if 13 <= ts.hour < 16 and safe:
            actions.append(action_step(
                step=step, start=ts, step_minutes=step_min,
                action_type="hvac_setpoint_delta", target_zone_keys=safe,
                setpoint_delta_c=0.5, reason="Smooth peak shaving in comfort-safe zones"))
    candidates.append(trajectory("smooth_peak_shave", start, horizon_steps, step_min,
                                 actions, "peak_smoothing"))

    actions = []
    for step in range(1, horizon_steps + 1):
        ts = start + timedelta(minutes=step_min * step)
        if empty:
            actions.append(action_step(
                step=step, start=ts, step_minutes=step_min,
                action_type="empty_zone_setback", target_zone_keys=empty,
                setpoint_delta_c=1.0, reason="Save HVAC in unoccupied zones"))
    candidates.append(trajectory("empty_zone_saver", start, horizon_steps, step_min,
                                 actions, "energy_saving"))

    actions = []
    for step in range(1, horizon_steps + 1):
        ts = start + timedelta(minutes=step_min * step)
        if safe:
            delta = 0.5 if step <= max(1, horizon_steps // 2) else 0.25
            actions.append(action_step(
                step=step, start=ts, step_minutes=step_min,
                action_type="comfort_safe_setback", target_zone_keys=safe,
                setpoint_delta_c=delta, lighting_factor=0.92 if large else None,
                reason="Gradual setback with low lighting trim"))
    candidates.append(trajectory("gradual_comfort_safe", start, horizon_steps, step_min,
                                 actions, "comfort_first"))

    actions = []
    for step in range(1, horizon_steps + 1):
        ts = start + timedelta(minutes=step_min * step)
        if 13 <= ts.hour < 16 and large:
            actions.append(action_step(
                step=step, start=ts, step_minutes=step_min,
                action_type="lighting_trim", target_zone_keys=large,
                lighting_factor=0.85, reason="Trim lighting in largest zones during peak"))
    candidates.append(trajectory("lighting_peak_trim", start, horizon_steps, step_min,
                                 actions, "load_smoothing"))
    return candidates


def _mods_for_step(candidate: dict, step: int) -> dict[str, dict]:
    mods: dict[str, dict] = {}
    for a in candidate.get("actions", []):
        if int(a.get("step") or 0) != step:
            continue
        for key in a.get("target_zone_keys") or []:
            rec = mods.setdefault(key, {"setpoint_delta_c": 0.0, "lighting_factor": 1.0})
            rec["setpoint_delta_c"] += float(a.get("setpoint_delta_c") or 0.0)
            if a.get("lighting_factor") is not None:
                rec["lighting_factor"] = min(rec["lighting_factor"], float(a["lighting_factor"]))
    return mods


def evaluate_trajectory(state: dict, candidate: dict,
                        *, weights: ObjectiveWeights | None = None) -> dict:
    step_h = int(state["metadata"]["timestep_minutes"]) / 60.0
    baseline_energy = optimized_energy = comfort_min = 0.0
    peak_kw = ramp_kw = 0.0
    prev_total = None
    action_changes = 0
    first_step_zone_states: list[dict] = []
    step_predictions = []
    model_meta = None
    for step in range(1, int(candidate["horizon_steps"]) + 1):
        mods = _mods_for_step(candidate, step)
        action_changes += len(mods)
        deltas = {k: v["setpoint_delta_c"] for k, v in mods.items()}
        rows = _rows_for_step(state, step, deltas)
        opt_kw, model_meta = _predict_total_kw(rows)
        base_kw = np.array([r["baseline_total_kw"] for r in rows], dtype=float)
        # Lighting factor is an explicit schedule modifier not learned by the
        # setpoint surrogate; apply it as a transparent delta.
        for i, r in enumerate(rows):
            factor = mods.get(r["zone_key"], {}).get("lighting_factor", 1.0)
            if factor < 1.0:
                opt_kw[i] = max(0.0, opt_kw[i] - r["baseline_lighting_kw"] * (1.0 - factor))
        step_total = float(opt_kw.sum())
        baseline_total = float(base_kw.sum())
        baseline_energy += baseline_total * step_h
        optimized_energy += step_total * step_h
        peak_kw = max(peak_kw, step_total)
        if prev_total is not None:
            ramp_kw = max(ramp_kw, abs(step_total - prev_total))
        prev_total = step_total
        step_comfort = 0.0
        zone_states = []
        for i, r in enumerate(rows):
            delta = mods.get(r["zone_key"], {}).get("setpoint_delta_c", 0.0)
            temp = r["baseline_temp_c"] + 0.4 * delta
            violated = r["occupancy_count"] >= 0.5 and temp > 26.5
            if violated:
                step_comfort += state["metadata"]["timestep_minutes"]
            zone_states.append({
                "zone_key": r["zone_key"],
                "total_power_kw": round(float(opt_kw[i]), 4),
                "hvac_power_kw": round(max(0.0, r["baseline_hvac_kw"] * (float(opt_kw[i]) / max(r["baseline_total_kw"], 0.001))), 4),
                "setpoint_c": round(r["cooling_setpoint_c"], 3),
                "temperature_c": round(temp, 3),
            })
        comfort_min += step_comfort
        if step == 1:
            first_step_zone_states = zone_states
        step_predictions.append({
            "step": step,
            "baseline_kw": round(baseline_total, 3),
            "optimized_kw": round(step_total, 3),
            "comfort_violation_min": round(step_comfort, 1),
        })
    policy_risk = 0.0
    objective = score_objective(
        energy_kwh=optimized_energy,
        peak_kw=peak_kw,
        comfort_minutes=comfort_min,
        ramp_kw=ramp_kw,
        action_changes=action_changes,
        policy_risk=policy_risk,
        weights=weights,
    )
    out = dict(candidate)
    out.update({
        "predicted": {
            "baseline_energy_kwh": round(baseline_energy, 3),
            "energy_kwh": round(optimized_energy, 3),
            "saving_kwh": round(baseline_energy - optimized_energy, 3),
            "peak_kw": round(peak_kw, 3),
            "comfort_violation_min": round(comfort_min, 1),
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
    execute_action = next((a for a in best.get("actions", []) if int(a.get("step") or 0) == 1), None)
    return {
        "metadata": {
            **state["metadata"],
            "control_mode": "predictive_receding_horizon",
            "horizon_steps": horizon,
            "top_k": top,
            "objective_version": "v1",
        },
        "selected": {k: v for k, v in best.items() if not k.startswith("_")},
        "execute_action": execute_action,
        "candidates": [{k: v for k, v in c.items() if not k.startswith("_")}
                       for c in scored[:max(1, top)]],
        "_first_step_zone_states": best.get("_first_step_zone_states", []),
    }

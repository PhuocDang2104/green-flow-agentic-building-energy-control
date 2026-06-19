"""Simulation tool: run what-if simulations and persist runs + KPI."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

from ...db import db_conn, fetch_all, fetch_one
from ...replayclock import anchor
from ...sim.actions import Action, zone_modifiers_at
from ...sim.kpi import compare_runs
from ...sim.runner import run_simulation
from ...sim.sim_store import read_run_series, write_run_rows
from ...sim.synthetic_baseline import SimRecord, SimResult, _fill_totals
from .db_tool import _clean

# Cooling electricity reduction per +1°C cooling setpoint (structural surrogate /
# EnergyPlus DoE ~ 5–10%/°C; use a conservative 6%).
HVAC_PCT_PER_C = 0.06

ROOT = Path(__file__).resolve().parents[4]
SEED_FILE = ROOT / "db" / "seed" / "normalized_building.json"
TZ = timezone(timedelta(hours=7))


def load_normalized() -> dict:
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def _result_from_telemetry(building_id: str, day_start) -> "SimResult | None":
    """Baseline = the REAL measured day (IPMVP M&V) from telemetry, not a synthetic
    re-simulation — so savings are computed against actual building operation and
    match the dashboard."""
    with db_conn() as conn:
        rows = fetch_all(conn, """
            SELECT z.entity_key AS zk, t.timestamp, t.temperature_c, t.setpoint_c,
                   t.occupancy_count, t.lighting_power_kw, t.plug_power_kw,
                   t.hvac_power_kw, t.total_power_kw, t.comfort_risk
            FROM telemetry_zone_15m t JOIN zones z ON z.id = t.zone_id
            WHERE t.building_id = :b AND t.timestamp >= :d
              AND t.timestamp < :d + interval '24 hours'
            ORDER BY t.timestamp
        """, b=building_id, d=day_start)
    if not rows:
        return None
    res = SimResult(engine="measured_baseline", step_minutes=30)
    for r in rows:
        loc = r["timestamp"].astimezone(TZ)
        res.records.append(SimRecord(
            minutes=loc.hour * 60 + loc.minute, zone_key=r["zk"],
            temperature_c=float(r["temperature_c"] or 25.0),
            setpoint_c=float(r["setpoint_c"] or 24.0),
            occupancy_count=float(r["occupancy_count"] or 0),
            lighting_kw=float(r["lighting_power_kw"] or 0),
            plug_kw=float(r["plug_power_kw"] or 0),
            hvac_kw=float(r["hvac_power_kw"] or 0),
            total_kw=float(r["total_power_kw"] or 0),
            comfort_violated=(r["comfort_risk"] == "high")))
    _fill_totals(res)
    return res


def _apply_actions(baseline: SimResult, actions: list[Action]) -> SimResult:
    """Optimized counterfactual = real baseline + transparent action effects
    (lighting dim factor, hvac off, setpoint raise -> HVAC_PCT_PER_C/°C)."""
    opt = SimResult(engine="measured_optimized", step_minutes=baseline.step_minutes)
    for r in baseline.records:
        hour = (r.minutes % 1440) / 60.0
        m = zone_modifiers_at(actions, r.zone_key, hour)
        d = m["setpoint_delta_c"]
        if m["hvac_off"]:
            hvac = 0.0
        elif d >= 0:
            hvac = r.hvac_kw * max(0.0, 1 - HVAC_PCT_PER_C * d)      # raise setpoint -> save
        else:
            hvac = r.hvac_kw * (1 + 0.04 * abs(d))                   # pre-cool -> small extra
        light = r.lighting_kw * m["lighting_factor"]
        total = light + r.plug_kw + hvac
        temp = r.temperature_c + d * 0.4
        opt.records.append(SimRecord(
            minutes=r.minutes, zone_key=r.zone_key, temperature_c=round(temp, 2),
            setpoint_c=round(r.setpoint_c + d, 2), occupancy_count=r.occupancy_count,
            lighting_kw=round(light, 3), plug_kw=r.plug_kw, hvac_kw=round(hvac, 3),
            total_kw=round(total, 3),
            comfort_violated=bool(r.occupancy_count >= 0.5 and temp > 26.5)))
    _fill_totals(opt)
    return opt


def simulate_actions(building_id: str, actions: list[Action],
                     *, persist: bool = True,
                     run_kind: str = "what_if") -> dict:
    """Baseline (REAL measured day if available, else synthetic) vs optimized
    counterfactual; returns KPI comparison."""
    day = anchor(building_id=building_id).astimezone(TZ).replace(
        hour=0, minute=0, second=0, microsecond=0)
    baseline = _result_from_telemetry(building_id, day)
    if baseline is not None:
        optimized = _apply_actions(baseline, actions)
    else:                                   # no telemetry -> synthetic fallback
        normalized = load_normalized()
        baseline = run_simulation(normalized, [])
        optimized = run_simulation(normalized, actions)
    kpi = compare_runs(baseline, optimized)
    result = {
        "engine": optimized.engine,
        "kpi": kpi,
        "actions": [a.to_dict() for a in actions],
    }
    if persist:
        with db_conn() as conn:
            base_id = _persist_run(conn, building_id, "baseline_fixed_schedule",
                                   "baseline", [], baseline, day)
            opt_id = _persist_run(conn, building_id, f"{run_kind}_run", run_kind,
                                  [a.to_dict() for a in actions], optimized, day)
            conn.execute(text("""
                INSERT INTO scenario_kpi (building_id, baseline_run_id, optimized_run_id,
                    baseline_kwh, optimized_kwh, saving_kwh, saving_percent,
                    cost_saving_vnd, peak_reduction_kw, comfort_violation_delta_min,
                    co2_avoided_kg, details_json)
                VALUES (:b, :base, :opt, :bk, :ok, :sk, :sp, :cs, :pr, :cd, :co2,
                        cast(:details as jsonb))
            """), {"b": building_id, "base": base_id, "opt": opt_id,
                   "bk": kpi["baseline_kwh"], "ok": kpi["optimized_kwh"],
                   "sk": kpi["saving_kwh"], "sp": kpi["saving_percent"],
                   "cs": kpi["cost_saving_vnd"], "pr": kpi["peak_reduction_kw"],
                   "cd": kpi["comfort_violation_delta_min"],
                   "co2": kpi["co2_avoided_kg"], "details": json.dumps(kpi)})
        result["baseline_run_id"] = str(base_id)
        result["optimized_run_id"] = str(opt_id)
    return result


def quick_estimate(action: Action, zones: list[dict]) -> dict:
    """Quick estimate (Level 1): LightGBM surrogate nếu có model, else rule thô.

    Surrogate (ml/scoring.estimate_action) học từ EnergyPlus DoE -> ước tính
    setpoint/lighting saving sát thực hơn rule tuyến tính. Fallback rule khi
    chưa có model file (deps optional)."""
    from ...ml.scoring import estimate_action
    surrogate = estimate_action(action, zones)
    if surrogate is not None:
        return surrogate

    target = [z for z in zones if not action.target_zone_keys
              or z["entity_key"] in action.target_zone_keys]
    area = sum(z.get("area_m2", 0) for z in target)
    hours = max(0.0, action.end_hour - action.start_hour)
    saving_kwh = 0.0
    if action.lighting_factor is not None:
        saving_kwh += area * 11 / 1000.0 * (1 - action.lighting_factor) * hours * 0.8
    if (action.setpoint_delta_c or 0) > 0:
        saving_kwh += area * 0.025 * action.setpoint_delta_c * hours
    return {"expected_saving_kwh": round(saving_kwh, 2),
            "zones_affected": len(target), "estimate_method": "rule_quick_estimate"}


def validate_baseline_against_telemetry(building_id: str,
                                        *, is_weekend: bool | None = None) -> dict:
    """Backtest: replay the synthetic no-action baseline against a real,
    fully-elapsed historical day and report how closely it tracks actual
    telemetry. The "Energy Saved"/"Peak Reduction" KPIs on Control &
    Simulation are deltas against this same baseline, so this answers the
    MVP_DELIVERY_PLAN.md risk "Simulation bị xem là giả" with a number
    instead of an assertion."""
    normalized = load_normalized()
    with db_conn() as conn:
        n_zones = fetch_one(conn, "SELECT count(*) n FROM zones WHERE building_id = :b",
                            b=building_id)["n"]
        days = fetch_all(conn, """
            SELECT day, n, (EXTRACT(ISODOW FROM day) IN (6, 7)) AS is_weekend
            FROM (SELECT date_trunc('day', timestamp) AS day, count(*) AS n
                  FROM telemetry_zone_15m WHERE building_id = :b GROUP BY 1) s
            ORDER BY day DESC LIMIT 14
        """, b=building_id)
        full_steps = n_zones * 96
        day = next((d for d in days if d["n"] >= full_steps
                   and (is_weekend is None or bool(d["is_weekend"]) == is_weekend)), None)
        if day is None:
            return {"error": "no fully-elapsed historical day available to validate against"}

        real_rows = fetch_all(conn, """
            SELECT z.entity_key AS zone_key, z.name AS zone_name,
                   t.timestamp, t.total_power_kw
            FROM telemetry_zone_15m t JOIN zones z ON z.id = t.zone_id
            WHERE t.building_id = :b AND t.timestamp >= :d AND t.timestamp < :d + interval '1 day'
        """, b=building_id, d=day["day"])

    sim = run_simulation(normalized, [], is_weekend=bool(day["is_weekend"]))
    sim_by_step: dict[int, dict[str, float]] = {}
    for r in sim.records:
        sim_by_step.setdefault(r.minutes, {})[r.zone_key] = r.total_kw

    real_by_step: dict[int, dict[str, float]] = {}
    zone_names: dict[str, str] = {}
    for r in real_rows:
        ts = r["timestamp"].astimezone(TZ)  # stored UTC; engine's "hour" is Hanoi local
        minutes = ts.hour * 60 + ts.minute
        real_by_step.setdefault(minutes, {})[r["zone_key"]] = float(r["total_power_kw"] or 0.0)
        zone_names[r["zone_key"]] = r["zone_name"]

    steps = sorted(set(real_by_step) & set(sim_by_step))
    series, abs_err, sq_err, real_total_kw, sim_total_kw = [], 0.0, 0.0, 0.0, 0.0
    for m in steps:
        real_kw = sum(real_by_step[m].values())
        sim_kw = sum(sim_by_step[m].values())
        series.append({"minutes": m, "time": f"{m // 60:02d}:{m % 60:02d}",
                       "real_kw": round(real_kw, 2), "sim_kw": round(sim_kw, 2)})
        abs_err += abs(real_kw - sim_kw)
        sq_err += (real_kw - sim_kw) ** 2
        real_total_kw += real_kw
        sim_total_kw += sim_kw
    n = len(steps) or 1
    mape = round(100.0 * abs_err / real_total_kw, 1) if real_total_kw else None
    rmse = round((sq_err / n) ** 0.5, 2)
    peak_real = max(series, key=lambda p: p["real_kw"]) if series else None
    peak_sim = max(series, key=lambda p: p["sim_kw"]) if series else None

    zone_errors = []
    for zk, name in zone_names.items():
        real_kwh = sum(real_by_step[m].get(zk, 0.0) for m in steps) / 4.0
        sim_kwh = sum(sim_by_step[m].get(zk, 0.0) for m in steps) / 4.0
        error_pct = round(100.0 * abs(real_kwh - sim_kwh) / real_kwh, 1) if real_kwh else None
        zone_errors.append({"zone_key": zk, "zone_name": name,
                            "real_kwh": round(real_kwh, 1), "sim_kwh": round(sim_kwh, 1),
                            "error_pct": error_pct})
    zone_errors.sort(key=lambda z: -(z["error_pct"] or 0))

    verdict = ("well calibrated" if mape is not None and mape <= 8
              else "acceptable, minor drift" if mape is not None and mape <= 20
              else "needs recalibration")
    return {
        "date": str(day["day"].date()), "is_weekend": bool(day["is_weekend"]),
        "engine": sim.engine,
        "real_kwh": round(real_total_kw / 4.0, 1), "sim_kwh": round(sim_total_kw / 4.0, 1),
        "mape_pct": mape, "rmse_kw": rmse, "verdict": verdict,
        "peak_real_kw": peak_real["real_kw"] if peak_real else None,
        "peak_real_time": peak_real["time"] if peak_real else None,
        "peak_sim_kw": peak_sim["sim_kw"] if peak_sim else None,
        "peak_sim_time": peak_sim["time"] if peak_sim else None,
        "series": series, "zones": zone_errors,
    }


def get_latest_comparison(building_id: str) -> dict:
    with db_conn() as conn:
        row = fetch_one(conn, """
            SELECT * FROM scenario_kpi WHERE building_id = :b
            ORDER BY computed_at DESC LIMIT 1
        """, b=building_id)
        return _clean(row) if row else {}


def get_run_series(run_id: str, metric: str = "total_power_kw") -> list[dict]:
    # Reads the wide sim_zone_15m table (spine storage, decision #3).
    with db_conn() as conn:
        return [_clean(r) for r in read_run_series(conn, run_id, metric)]


def _persist_run(conn, building_id: str, label: str, kind: str,
                 actions_json: list, result: SimResult, day_start) -> uuid.UUID:
    run_id = uuid.uuid4()
    conn.execute(text("""
        INSERT INTO simulation_runs (id, building_id, baseline_label, run_kind, engine,
                                     actions_json, status, completed_at, notes)
        VALUES (:id, :b, :label, :kind, :engine, cast(:actions as jsonb), 'completed',
                now(), :notes)
    """), {"id": run_id, "b": building_id, "label": label, "kind": kind,
           "engine": result.engine, "actions": json.dumps(actions_json),
           "notes": f"totals: {json.dumps(result.totals)}"})
    zone_ids = {z["entity_key"]: z["id"] for z in fetch_all(
        conn, "SELECT id, entity_key FROM zones WHERE building_id = :b", b=building_id)}
    write_run_rows(conn, run_id, result, zone_ids, day_start)
    return run_id

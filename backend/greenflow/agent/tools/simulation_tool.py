"""Simulation tool: run what-if simulations and persist runs + KPI."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

from ...db import db_conn, fetch_all, fetch_one
from ...sim.actions import Action
from ...sim.kpi import compare_runs
from ...sim.runner import run_simulation
from ...sim.synthetic_baseline import SimResult
from .db_tool import _clean

ROOT = Path(__file__).resolve().parents[4]
SEED_FILE = ROOT / "db" / "seed" / "normalized_building.json"
TZ = timezone(timedelta(hours=7))


def load_normalized() -> dict:
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def simulate_actions(building_id: str, actions: list[Action],
                     *, persist: bool = True,
                     run_kind: str = "what_if") -> dict:
    """Baseline + action run on identical inputs; returns KPI comparison."""
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
        day = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
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
    """Rule-based quick estimate without running a simulation (Level 1)."""
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


def get_latest_comparison(building_id: str) -> dict:
    with db_conn() as conn:
        row = fetch_one(conn, """
            SELECT * FROM scenario_kpi WHERE building_id = :b
            ORDER BY computed_at DESC LIMIT 1
        """, b=building_id)
        return _clean(row) if row else {}


def get_run_series(run_id: str, metric: str = "total_power_kw") -> list[dict]:
    with db_conn() as conn:
        return [_clean(r) for r in fetch_all(conn, """
            SELECT timestamp, sum(metric_value) AS value
            FROM simulation_results
            WHERE simulation_run_id = :r AND metric_name = :m
            GROUP BY timestamp ORDER BY timestamp
        """, r=run_id, m=metric)]


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
    rows = []
    for r in result.records:
        ts = day_start + timedelta(minutes=r.minutes)
        zid = zone_ids.get(r.zone_key)
        for metric, value, unit in (
            ("zone_temperature_c", r.temperature_c, "C"),
            ("hvac_power_kw", r.hvac_kw, "kW"),
            ("lighting_power_kw", r.lighting_kw, "kW"),
            ("total_power_kw", r.total_kw, "kW"),
            ("comfort_violated", 1.0 if r.comfort_violated else 0.0, "bool"),
        ):
            rows.append({"run": run_id, "ts": ts, "z": zid, "m": metric,
                         "v": value, "u": unit})
    if rows:
        conn.execute(text("""
            INSERT INTO simulation_results (simulation_run_id, timestamp, zone_id,
                                            metric_name, metric_value, metric_unit)
            VALUES (:run, :ts, :z, :m, :v, :u)
        """), rows)
    return run_id

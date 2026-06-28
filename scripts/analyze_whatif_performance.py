"""Analyze precomputed predictive-MPC what-if cache performance.

This is a read-only diagnostic script. It summarizes energy, demand, action
mix, setpoint movement, lighting trim, and weak periods from the materialized
what-if cache.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from greenflow.config import get_settings  # noqa: E402
from greenflow.control.whatif_cache import (  # noqa: E402
    CONTROL_MODE,
    _completed_cache_key,
    ensure_schema,
    parse_local_date,
    validate_cache_range,
)
from greenflow.datasets import active_dataset  # noqa: E402
from greenflow.db import db_conn, fetch_all  # noqa: E402


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _jsonish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date-from", required=True)
    ap.add_argument("--date-to", required=True)
    ap.add_argument("--scenario-id", default=None)
    ap.add_argument("--horizon-steps", type=int, default=get_settings().greenflow_control_horizon_steps)
    ap.add_argument("--top-k", type=int, default=get_settings().greenflow_control_top_k)
    ap.add_argument("--building-id", default=get_settings().default_building_id)
    ap.add_argument("--min-saving-percent", type=float, default=0.0)
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    ds = active_dataset()
    scenario = args.scenario_id or ds.scenario_id
    start = parse_local_date(args.date_from)
    end = parse_local_date(args.date_to)
    if start is None or end is None or start >= end:
        raise SystemExit("date-from/date-to are required and date-from must be before date-to")

    validation = validate_cache_range(
        date_from=start.isoformat(),
        date_to=end.isoformat(),
        scenario_id=scenario,
        horizon_steps=args.horizon_steps,
        top_k=args.top_k,
        building_id=args.building_id,
        min_saving_percent=args.min_saving_percent,
    )

    with db_conn() as conn:
        ensure_schema(conn)
        key_row = _completed_cache_key(
            conn,
            ds=ds,
            scenario_id=scenario,
            horizon_steps=args.horizon_steps,
            top_k=args.top_k,
            start=start,
            end=end,
        )
        if not key_row:
            raise SystemExit("cache not found")
        cache_key = key_row["cache_key"]
        daily = fetch_all(conn, """
            SELECT d.date, d.baseline_kwh, d.ai_kwh, d.saving_kwh,
                   d.saving_percent, d.baseline_peak_kw, d.ai_peak_kw,
                   d.action_count, d.comfort_violation_min
            FROM whatif_cache_daily d
            JOIN whatif_cache_runs r ON r.id = d.run_id
            WHERE r.cache_key = :cache_key
              AND r.status = 'complete'
              AND d.date >= :date_from
              AND d.date < :date_to
            ORDER BY d.date
        """, cache_key=cache_key, date_from=start, date_to=end)
        steps = fetch_all(conn, """
            SELECT t.timestamp, t.baseline_kw, t.ai_kw, t.baseline_kwh,
                   t.ai_kwh, t.saving_kwh, t.selected_trajectory,
                   t.objective_score, t.action_json
            FROM whatif_cache_timestep t
            JOIN whatif_cache_runs r ON r.id = t.run_id
            WHERE r.cache_key = :cache_key
              AND r.status = 'complete'
              AND t.timestamp >= CAST(:date_from AS timestamptz)
              AND t.timestamp < CAST(:date_to AS timestamptz)
            ORDER BY t.timestamp
        """, cache_key=cache_key, date_from=f"{start.isoformat()} 00:00:00+07:00",
            date_to=f"{end.isoformat()} 00:00:00+07:00")

    trajectory_counts = Counter(str(r.get("selected_trajectory") or "none") for r in steps)
    action_type_counts: Counter[str] = Counter()
    action_records = 0
    action_zone_targets = 0
    setpoint_action_records = 0
    setpoint_zone_targets = 0
    setpoint_delta_zone_sum = 0.0
    lighting_action_records = 0
    lighting_zone_targets = 0
    lighting_reduction_zone_sum = 0.0

    for row in steps:
        actions = _jsonish(row.get("action_json")) or []
        if not isinstance(actions, list):
            continue
        for action in actions:
            if not isinstance(action, dict):
                continue
            targets = action.get("target_zone_keys") or []
            target_count = len(targets)
            action_records += 1
            action_zone_targets += target_count
            action_type = str(action.get("action_type") or "unknown")
            action_type_counts[action_type] += 1
            setpoint_delta = _f(action.get("setpoint_delta_c"))
            if setpoint_delta:
                setpoint_action_records += 1
                setpoint_zone_targets += target_count
                setpoint_delta_zone_sum += setpoint_delta * target_count
            if action.get("lighting_factor") is not None:
                factor = _f(action.get("lighting_factor"), 1.0)
                lighting_action_records += 1
                lighting_zone_targets += target_count
                lighting_reduction_zone_sum += max(0.0, 1.0 - factor) * target_count

    baseline_peak = max((_f(r.get("baseline_kw")) for r in steps), default=0.0)
    ai_peak = max((_f(r.get("ai_kw")) for r in steps), default=0.0)
    total_baseline = sum(_f(r.get("baseline_kwh")) for r in steps)
    total_ai = sum(_f(r.get("ai_kwh")) for r in steps)
    total_saving = total_baseline - total_ai
    negative_steps = [r for r in steps if _f(r.get("saving_kwh")) < 0]

    best_days = sorted(daily, key=lambda r: _f(r.get("saving_kwh")), reverse=True)[:args.limit]
    worst_days = sorted(daily, key=lambda r: _f(r.get("saving_kwh")))[:args.limit]
    best_steps = sorted(steps, key=lambda r: _f(r.get("saving_kwh")), reverse=True)[:args.limit]
    worst_steps = sorted(steps, key=lambda r: _f(r.get("saving_kwh")))[:args.limit]

    result = {
        "cache_key": cache_key,
        "dataset": ds.to_metadata(),
        "validation": validation,
        "summary_from_timesteps": {
            "steps": len(steps),
            "baseline_kwh": round(total_baseline, 3),
            "ai_kwh": round(total_ai, 3),
            "saving_kwh": round(total_saving, 3),
            "saving_percent": round(total_saving / total_baseline * 100.0, 3) if total_baseline else 0.0,
            "baseline_peak_kw": round(baseline_peak, 3),
            "ai_peak_kw": round(ai_peak, 3),
            "peak_reduction_kw": round(baseline_peak - ai_peak, 3),
            "peak_reduction_percent": round((baseline_peak - ai_peak) / baseline_peak * 100.0, 3)
            if baseline_peak else 0.0,
            "negative_saving_steps": len(negative_steps),
        },
        "action_mix": {
            "action_records": action_records,
            "action_zone_targets": action_zone_targets,
            "by_action_type": dict(action_type_counts.most_common()),
            "selected_trajectories": dict(trajectory_counts.most_common()),
            "setpoint_action_records": setpoint_action_records,
            "setpoint_zone_targets": setpoint_zone_targets,
            "avg_setpoint_delta_per_target_zone_c": round(
                setpoint_delta_zone_sum / setpoint_zone_targets, 4
            ) if setpoint_zone_targets else 0.0,
            "lighting_action_records": lighting_action_records,
            "lighting_zone_targets": lighting_zone_targets,
            "avg_lighting_reduction_per_target_zone_pct": round(
                lighting_reduction_zone_sum / lighting_zone_targets * 100.0, 3
            ) if lighting_zone_targets else 0.0,
        },
        "best_days": [dict(r) for r in best_days],
        "worst_days": [dict(r) for r in worst_days],
        "best_steps": [dict(r) for r in best_steps],
        "worst_steps": [dict(r) for r in worst_steps],
        "interpretation": [
            "Energy/Power come directly from precomputed replay baseline_kw/ai_kw.",
            "Comfort and setpoint are derived building averages from telemetry plus stored MPC action deltas.",
            "Electrical loading is normalized to selected-range baseline peak, not a measured MSB/DB rating.",
        ],
    }
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
    return 0 if validation.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

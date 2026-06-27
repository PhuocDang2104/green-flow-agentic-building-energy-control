"""Step-by-step validation replay for predictive control.

Baseline is persisted EnergyPlus telemetry. The AI branch is a receding-horizon
counterfactual: at each recorded timestamp the controller evaluates candidate
trajectories with the surrogate provider, executes only the first step, then the
resulting zone state is fed into the next timestep as an override.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..datasets import active_dataset
from ..db import db_conn, fetch_all
from .predictive import run_predictive_control

TZ = timezone(timedelta(hours=7))


def _local(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=TZ)
    return value.astimezone(TZ)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _local(value).isoformat()
    return str(value)


def _timestamps(building_id: str, *, scenario_id: str | None,
                date_from: str | None, date_to: str | None,
                max_steps: int) -> list[datetime]:
    with db_conn() as conn:
        rows = fetch_all(conn, """
            SELECT DISTINCT timestamp
            FROM telemetry_zone_15m
            WHERE building_id = :b
              AND (CAST(:scn AS text) IS NULL
                   OR scenario_id = CAST(:scn AS text)
                   OR scenario_id IS NULL)
              AND (CAST(:df AS timestamptz) IS NULL OR timestamp >= CAST(:df AS timestamptz))
              AND (CAST(:dt AS timestamptz) IS NULL OR timestamp < CAST(:dt AS timestamptz))
            ORDER BY timestamp
            LIMIT :lim
        """, b=building_id, scn=scenario_id, df=date_from, dt=date_to,
                      lim=max(1, int(max_steps)))
    return [_local(r["timestamp"]) for r in rows]


def _overrides_from_zone_states(states: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for z in states:
        key = z.get("zone_key")
        if not key:
            continue
        out[str(key)] = {
            "temperature_c": z.get("temperature_c"),
            "setpoint_c": z.get("setpoint_c"),
            "hvac_power_kw": z.get("hvac_power_kw"),
            "total_power_kw": z.get("total_power_kw"),
        }
    return out


def run_predictive_replay(building_id: str, *, date_from: str | None = None,
                          date_to: str | None = None, max_steps: int = 96,
                          horizon_steps: int | None = None,
                          top_k: int | None = None,
                          scenario_id: str | None = None) -> dict:
    ds = active_dataset()
    scenario = scenario_id or ds.scenario_id
    stamps = _timestamps(building_id, scenario_id=scenario, date_from=date_from,
                         date_to=date_to, max_steps=max_steps)
    if not stamps:
        return {
            "metadata": {**ds.to_metadata(), "building_id": building_id,
                         "scenario_id": scenario, "status": "no_telemetry"},
            "summary": {},
            "series": [],
            "actions": [],
        }

    step_h = ds.timestep_minutes / 60.0
    overrides: dict[str, dict] = {}
    series: list[dict] = []
    actions: list[dict] = []
    errors: list[dict] = []

    for ts in stamps:
        try:
            res = run_predictive_control(
                building_id,
                timestamp=ts.isoformat(),
                scenario_id=scenario,
                horizon_steps=horizon_steps,
                top_k=top_k,
                state_overrides=overrides,
            )
            selected = res["selected"]
            first = (selected.get("step_predictions") or [{}])[0]
            baseline_kw = float(first.get("baseline_kw") or 0.0)
            ai_kw = float(first.get("optimized_kw") or baseline_kw)
            comfort_min = float(first.get("comfort_violation_min") or 0.0)
            series.append({
                "timestamp": ts.isoformat(),
                "baseline_kw": round(baseline_kw, 4),
                "ai_kw": round(ai_kw, 4),
                "baseline_kwh": round(baseline_kw * step_h, 4),
                "ai_kwh": round(ai_kw * step_h, 4),
                "saving_kwh": round((baseline_kw - ai_kw) * step_h, 4),
                "comfort_violation_min": round(comfort_min, 2),
                "selected_trajectory": selected.get("id"),
                "objective_score": selected.get("objective", {}).get("score"),
            })
            action = res.get("execute_action")
            if action:
                actions.append({"timestamp": ts.isoformat(), **action})
            overrides = _overrides_from_zone_states(res.get("_first_step_zone_states") or [])
        except Exception as exc:  # noqa: BLE001 - keep replay evidence instead of aborting
            errors.append({"timestamp": ts.isoformat(), "error": repr(exc)[:240]})
            overrides = {}

    baseline_kwh = sum(r["baseline_kwh"] for r in series)
    ai_kwh = sum(r["ai_kwh"] for r in series)
    summary = {
        "steps": len(series),
        "errors": len(errors),
        "baseline_kwh": round(baseline_kwh, 3),
        "ai_kwh": round(ai_kwh, 3),
        "saving_kwh": round(baseline_kwh - ai_kwh, 3),
        "saving_percent": round((baseline_kwh - ai_kwh) / baseline_kwh * 100.0, 3)
        if baseline_kwh else 0.0,
        "baseline_peak_kw": round(max((r["baseline_kw"] for r in series), default=0.0), 3),
        "ai_peak_kw": round(max((r["ai_kw"] for r in series), default=0.0), 3),
        "comfort_violation_min": round(sum(r["comfort_violation_min"] for r in series), 2),
        "date_from": _iso(stamps[0]),
        "date_to": _iso(stamps[-1] + timedelta(minutes=ds.timestep_minutes)),
    }
    return {
        "metadata": {
            **ds.to_metadata(),
            "building_id": building_id,
            "scenario_id": scenario,
            "validation_mode": "baseline_eplus_vs_ai_surrogate_receding_horizon",
            "horizon_steps": horizon_steps,
            "top_k": top_k,
        },
        "summary": summary,
        "series": series,
        "actions": actions,
        "errors": errors,
    }

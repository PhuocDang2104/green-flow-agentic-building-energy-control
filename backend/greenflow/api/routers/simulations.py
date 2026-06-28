"""Simulation APIs: runs, series, baseline-vs-optimized comparison."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from ...agent import service
from ...agent.tools import simulation_tool
from ...agent.tools.db_tool import _clean
from ...db import db_conn, fetch_all, fetch_one
from ..deps import default_building_id

router = APIRouter()
TZ = timezone(timedelta(hours=7))


def _local_bound(value: str | None) -> datetime | None:
    """Interpret date-only API filters as Hanoi local dates.

    PostgreSQL casts bare `2024-03-01` as UTC in this stack, which shifts the
    campaign/replay window by seven hours and creates partial extra local days.
    """
    if not value:
        return None
    s = value.strip()
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


@router.get("/simulations")
def list_runs(building_id: str = Query(default=None), limit: int = 20):
    with db_conn() as conn:
        rows = [_clean(r) for r in fetch_all(conn, """
            SELECT id, baseline_label, run_kind, engine, actions_json, status,
                   started_at, completed_at, notes
            FROM simulation_runs WHERE building_id = :b
            ORDER BY started_at DESC LIMIT :lim
        """, b=building_id or default_building_id(), lim=limit)]
    for r in rows:
        notes = r.pop("notes", "") or ""
        if notes.startswith("totals: "):
            try:
                r["totals"] = json.loads(notes[len("totals: "):])
            except json.JSONDecodeError:
                pass
    return rows


@router.get("/simulations/compare/latest")
def latest_comparison(building_id: str = Query(default=None)):
    result = simulation_tool.get_latest_comparison(
        building_id or default_building_id())
    if not result:
        raise HTTPException(404, "no comparison available; run an optimization first")
    return result


@router.get("/simulations/compare/series")
def comparison_series(building_id: str = Query(default=None),
                      metric: str = "total_power_kw"):
    """Aligned baseline + optimized series for the latest comparison."""
    b = building_id or default_building_id()
    comparison = simulation_tool.get_latest_comparison(b)
    if not comparison:
        raise HTTPException(404, "no comparison available")
    baseline = simulation_tool.get_run_series(comparison["baseline_run_id"], metric)
    optimized = simulation_tool.get_run_series(comparison["optimized_run_id"], metric)
    opt_by_ts = {r["timestamp"]: r["value"] for r in optimized}
    return {
        "metric": metric,
        "kpi": comparison.get("details_json"),
        "baseline_run_id": comparison["baseline_run_id"],
        "optimized_run_id": comparison["optimized_run_id"],
        "series": [{
            "timestamp": r["timestamp"],
            "baseline": r["value"],
            "optimized": opt_by_ts.get(r["timestamp"]),
        } for r in baseline],
    }


@router.get("/simulations/validate-baseline")
def validate_baseline(building_id: str = Query(default=None),
                      is_weekend: bool | None = Query(default=None)):
    """Backtest the no-action synthetic baseline against a real historical
    day's telemetry (Control & Simulation -> Model Validation panel)."""
    result = simulation_tool.validate_baseline_against_telemetry(
        building_id or default_building_id(), is_weekend=is_weekend)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.get("/simulations/whatif-cache")
def whatif_cache(mode: str = Query(default="predictive_replay"),
                 date_from: str | None = Query(default=None),
                 date_to: str | None = Query(default=None),
                 scenario_id: str | None = Query(default=None),
                 horizon_steps: int | None = Query(default=None),
                 top_k: int | None = Query(default=None),
                 resolution: str = Query(default="auto")):
    """Read precomputed what-if/MPC replay data.

    This endpoint intentionally does not run predictive replay on cache miss;
    long replay belongs to scripts/precompute_predictive_whatif.py.
    """
    from ...control.whatif_cache import read_cache_response

    try:
        return read_cache_response(
            mode=mode,
            date_from=date_from,
            date_to=date_to,
            scenario_id=scenario_id,
            horizon_steps=horizon_steps,
            top_k=top_k,
            resolution=resolution,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@router.get("/simulations/{run_id}")
def get_run(run_id: str):
    with db_conn() as conn:
        run = fetch_one(conn, "SELECT * FROM simulation_runs WHERE id = :r", r=run_id)
    if not run:
        raise HTTPException(404, "simulation run not found")
    return _clean(run)


@router.get("/simulations/{run_id}/series")
def run_series(run_id: str, metric: str = "total_power_kw"):
    return simulation_tool.get_run_series(run_id, metric)


@router.delete("/simulations/{run_id}")
def delete_run(run_id: str):
    """Delete a scenario run. sim_zone_15m rows cascade; scenario_kpi refs null."""
    with db_conn() as conn:
        row = fetch_one(conn, "DELETE FROM simulation_runs WHERE id = :r RETURNING id",
                        r=run_id)
    if not row:
        raise HTTPException(404, "simulation run not found")
    return {"deleted": run_id}


class ScenarioRequest(BaseModel):
    building_id: str | None = None
    apply_ai: bool = True
    strategy: str = "optimization"   # optimization | peak
    horizon_minutes: int = 60
    label: str | None = None


@router.post("/simulations/scenario")
def create_scenario(req: ScenarioRequest, background: BackgroundTasks):
    """Create a scenario. apply_ai=false -> a baseline (no-action) run, persisted
    immediately. apply_ai=true -> the agent optimizes (or peak-shaves) with the
    given parameters and simulates the result in the background."""
    b = req.building_id or default_building_id()
    if not req.apply_ai:
        rid = simulation_tool.persist_baseline_only(b, req.label)
        return {"run_id": rid, "status": "completed", "mode": "baseline"}
    sc: dict = {"horizon_minutes": req.horizon_minutes}
    action = "run_optimization"
    if req.strategy == "peak":
        action = "peak_strategy"
        sc["peak_strategy"] = True
    run_id = service.start_run(b, "button", button_action=action, scenario_config=sc)
    background.add_task(service.execute_run, run_id, b, "button",
                        button_action=action, scenario_config=sc)
    return {"run_id": run_id, "status": "running", "mode": "ai"}


class SimulateRequest(BaseModel):
    building_id: str | None = None
    scenario_config: dict = {}


@router.post("/simulation/simulate-recommended-actions")
def simulate_recommended(req: SimulateRequest, background: BackgroundTasks):
    """Control Agent proposes strategies -> Simulation Agent tests them
    (peak_strategy workflow without execution emphasis)."""
    b = req.building_id or default_building_id()
    run_id = service.start_run(b, "button", button_action="peak_strategy",
                               scenario_config=req.scenario_config)
    background.add_task(service.execute_run, run_id, b, "button",
                        button_action="peak_strategy",
                        scenario_config=req.scenario_config)
    return {"run_id": run_id, "status": "running"}


class CampaignRequest(BaseModel):
    building_id: str | None = None
    setpoint_delta: float = 1.0           # AI policy: raise cooling setpoint by N°C
    peak_start: int = 13
    peak_end: int = 16
    date_from: str | None = None          # ISO; default = full telemetry range
    date_to: str | None = None
    scenario_id: str | None = None


@router.post("/simulations/campaign")
def run_campaign(req: CampaignRequest):
    """Period (campaign) what-if: building WITHOUT AI vs WITH a fixed setpoint
    policy over the whole date range. baseline = measured; with-AI = measured
    minus the structural surrogate's predicted reduction. Not the in-loop
    approve sim — one fixed policy rolled across every step (Phase 3)."""
    import pandas as pd

    from ...ml import campaign_whatif
    b = req.building_id or default_building_id()
    date_from = _local_bound(req.date_from)
    date_to = _local_bound(req.date_to)
    with db_conn() as conn:
        rows = fetch_all(conn, """
            SELECT t.timestamp, t.total_power_kw, t.temperature_c, t.occupancy_count,
                   COALESCE(t.setpoint_c, 24) AS cooling_setpoint_c,
                   COALESCE(z.area_m2, 50) AS area_m2,
                   COALESCE(z.volume_m3, COALESCE(z.area_m2, 50) * 3) AS volume_m3,
                   3.0 AS ceiling_height_m,
                   COALESCE(w.outdoor_temp_c, 30) AS outdoor_temp_c,
                   COALESCE(w.humidity_pct, 70) AS outdoor_rh_pct,
                   COALESCE(w.solar_w_m2, 0) AS ghi,
                   COALESCE(w.wind_speed_mps, 2) AS wind,
                   COALESCE(w.cloud_cover_pct, 40) AS cloud
            FROM telemetry_zone_15m t
            JOIN zones z ON z.id = t.zone_id
            LEFT JOIN (SELECT DISTINCT ON (timestamp) timestamp, outdoor_temp_c,
                              humidity_pct, solar_w_m2, wind_speed_mps, cloud_cover_pct
                       FROM weather_15m ORDER BY timestamp) w ON w.timestamp = t.timestamp
            WHERE t.building_id = :b
              AND (CAST(:scn AS text) IS NULL
                   OR t.scenario_id = CAST(:scn AS text)
                   OR t.scenario_id IS NULL)
              AND (CAST(:df AS timestamptz) IS NULL OR t.timestamp >= CAST(:df AS timestamptz))
              AND (CAST(:dt AS timestamptz) IS NULL OR t.timestamp < CAST(:dt AS timestamptz))
            ORDER BY t.timestamp
        """, b=b, scn=req.scenario_id, df=date_from, dt=date_to)
    if not rows:
        raise HTTPException(404, "no telemetry for the period")
    df = pd.DataFrame([dict(r) for r in rows])
    # telemetry is timestamptz (UTC); the peak window is LOCAL — convert to Hanoi
    # before extracting hour, else 13-16h lands on the wrong (UTC) hours.
    ts = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("Asia/Ho_Chi_Minh")
    # Keep the localized timestamp for downstream daily aggregation as well.
    # Otherwise a local 00:00-07:00 sample is grouped under the previous UTC
    # date, which makes month/day filters appear one day early in the chart.
    df["timestamp"] = ts
    df["hour"] = ts.dt.hour
    df["dow"] = ts.dt.dayofweek
    df["month"] = ts.dt.month
    df["office_hours_flag"] = ((df.hour >= 7) & (df.hour < 19) & (df.dow < 5)).astype(int)
    result = campaign_whatif.compute_campaign(
        df, setpoint_delta=req.setpoint_delta,
        peak_start=req.peak_start, peak_end=req.peak_end)
    if result is None:
        raise HTTPException(503, "surrogate model unavailable")
    from ...datasets import active_dataset
    result.setdefault("metadata", {})
    result["metadata"].update({
        "dataset": active_dataset().to_metadata(),
        "scenario_id": req.scenario_id,
        "control_mode": "fixed_policy_campaign",
    })
    return result


class PredictiveControlRequest(BaseModel):
    building_id: str | None = None
    timestamp: str | None = None
    scenario_id: str | None = None
    horizon_steps: int | None = None
    top_k: int | None = None


@router.post("/simulations/predictive-control")
def predictive_control(req: PredictiveControlRequest):
    """Run one receding-horizon control decision."""
    from ...control.predictive import run_predictive_control

    try:
        return run_predictive_control(
            req.building_id or default_building_id(),
            timestamp=req.timestamp,
            scenario_id=req.scenario_id,
            horizon_steps=req.horizon_steps,
            top_k=req.top_k,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc))


class PredictiveReplayRequest(BaseModel):
    building_id: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    max_steps: int = 96
    scenario_id: str | None = None
    horizon_steps: int | None = None
    top_k: int | None = None


@router.post("/simulations/predictive-replay")
def predictive_replay(req: PredictiveReplayRequest):
    """Validate E+ baseline against AI receding-horizon surrogate control."""
    from ...control.replay import run_predictive_replay

    return run_predictive_replay(
        req.building_id or default_building_id(),
        date_from=req.date_from,
        date_to=req.date_to,
        max_steps=req.max_steps,
        scenario_id=req.scenario_id,
        horizon_steps=req.horizon_steps,
        top_k=req.top_k,
    )

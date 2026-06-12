"""Simulation APIs: runs, series, baseline-vs-optimized comparison."""

from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from ...agent import service
from ...agent.tools import simulation_tool
from ...agent.tools.db_tool import _clean
from ...db import db_conn, fetch_all, fetch_one
from ..deps import default_building_id

router = APIRouter()


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

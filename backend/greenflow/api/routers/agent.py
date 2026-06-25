"""Agent APIs: button workflows, chatbot, run status/logs."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from ...agent import service
from ...agent.tools.db_tool import _clean
from ...db import db_conn, fetch_all
from ..deps import default_building_id

router = APIRouter(prefix="/agent")


class RunRequest(BaseModel):
    building_id: str | None = None
    scenario_config: dict = {}
    session_id: str | None = None  # chat session to post the run report into


def _start_button_run(button_action: str, req: RunRequest,
                      background: BackgroundTasks) -> dict:
    b = req.building_id or default_building_id()
    run_id = service.start_run(b, "button", button_action=button_action,
                               scenario_config=req.scenario_config,
                               session_id=req.session_id)
    background.add_task(service.execute_run, run_id, b, "button",
                        button_action=button_action,
                        scenario_config=req.scenario_config,
                        session_id=req.session_id)
    return {"run_id": run_id, "status": "running", "button_action": button_action}


@router.post("/run-optimization")
def run_optimization(req: RunRequest, background: BackgroundTasks):
    return _start_button_run("run_optimization", req, background)


@router.post("/predict")
def run_prediction(req: RunRequest, background: BackgroundTasks):
    return _start_button_run("run_prediction", req, background)


@router.post("/peak-strategy")
def peak_strategy(req: RunRequest, background: BackgroundTasks):
    return _start_button_run("peak_strategy", req, background)


@router.post("/compare-baseline-optimized")
def compare_baseline(req: RunRequest, background: BackgroundTasks):
    return _start_button_run("compare_baseline_optimized", req, background)


@router.post("/report/building-semantic")
def report_building_semantic(req: RunRequest, background: BackgroundTasks):
    return _start_button_run("building_semantic_report", req, background)


@router.post("/report/hvac-elec")
def report_hvac_elec(req: RunRequest, background: BackgroundTasks):
    return _start_button_run("hvac_elec_report", req, background)


@router.post("/scan-anomalies")
def scan_anomalies_endpoint(req: RunRequest):
    """Run the anomaly engine over the last 24h of the replay clock and write
    alerts (idempotent rescan)."""
    from datetime import timedelta
    from ...agent.anomaly import scan_anomalies
    from ...replayclock import anchor
    b = req.building_id or default_building_id()
    with db_conn() as conn:
        now = anchor(conn, b)
        n = scan_anomalies(conn, b, now - timedelta(hours=24), now)
    return {"alerts_written": n, "window_end": str(now)}


@router.get("/runs")
def list_runs(building_id: str = Query(default=None), limit: int = 20):
    with db_conn() as conn:
        return [_clean(r) for r in fetch_all(conn, """
            SELECT id, entrypoint, button_action, user_query, intent, status,
                   started_at, finished_at, final_answer
            FROM agent_runs WHERE building_id = :b
            ORDER BY started_at DESC LIMIT :lim
        """, b=building_id or default_building_id(), lim=limit)]


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run


@router.get("/runs/{run_id}/logs")
def get_run_logs(run_id: str):
    return service.get_run_logs(run_id)

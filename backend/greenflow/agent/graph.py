"""Main LangGraph: input_router -> intent -> planner -> plan_executor ->
response_composer -> audit_logger.

The plan executor walks the orchestration plan sequentially, dispatching to
node functions and appending an agent_logs row (DB) after each step so the UI
can stream progress like a CI pipeline.
"""

from __future__ import annotations

import json
import time
import uuid

from langgraph.graph import END, START, StateGraph
from sqlalchemy import text

from ..db import db_conn
from .nodes import (building_semantic, composer, control, execution, intent,
                    planner, policy_node, prediction, report, simulation)
from .state import GreenFlowState
from .tools import simulation_tool

NODE_LABELS = {
    "input_router": "Input Router",
    "intent_classifier": "Intent Classifier",
    "orchestration_planner": "Orchestration Planner",
    "building_semantic": "Building Semantic Agent",
    "prediction": "Prediction Agent",
    "control": "Control Agent",
    "simulation": "Simulation Agent",
    "policy": "Policy Engine",
    "execution": "Execution / Approval",
    "compare": "Baseline Comparator",
    "report": "Report Agent",
    "response_composer": "Response Composer",
    "audit_logger": "Audit Logger",
}

PLAN_NODES = {
    "building_semantic": building_semantic.run,
    "prediction": prediction.run,
    "control": control.run,
    "simulation": simulation.run,
    "policy": policy_node.run,
    "execution": execution.run,
    "report": report.run,
}


def _compare(state: GreenFlowState) -> dict:
    latest = simulation_tool.get_latest_comparison(state["building_id"])
    kpi = latest.get("details_json") or {}
    if isinstance(kpi, str):
        kpi = json.loads(kpi)
    return {"baseline_vs_optimized": kpi or latest}


PLAN_NODES["compare"] = _compare


def _log_step(state: GreenFlowState, step: int, node: str, status: str,
              message: str, duration_ms: int, summary: dict | None = None) -> dict:
    entry = {"step": step, "node": NODE_LABELS.get(node, node), "status": status,
             "message": message, "duration_ms": duration_ms,
             "output_summary": summary or {}}
    run_id = state.get("run_id")
    if run_id:
        try:
            with db_conn() as conn:
                conn.execute(text("""
                    INSERT INTO agent_logs (run_id, step, node, status, message,
                                            duration_ms, output_summary)
                    VALUES (:r, :s, :n, :st, :m, :d, cast(:o as jsonb))
                """), {"r": run_id, "s": step, "n": entry["node"], "st": status,
                       "m": message, "d": duration_ms,
                       "o": json.dumps(entry["output_summary"], default=str)})
        except Exception:
            pass  # logging must never break the run
    return entry


def _summarize(node: str, update: dict) -> tuple[str, dict]:
    if node == "building_semantic":
        sc = update.get("semantic_context", {})
        n_findings = len(update.get("abnormal_findings", []))
        return (f"Loaded semantic graph: {sc.get('zone_count', 0)} zones, "
                f"{sc.get('device_count', 0)} devices; {n_findings} abnormal finding(s).",
                {"zones": sc.get("zone_count"), "findings": n_findings,
                 "missing_metadata": len(update.get("missing_metadata", []))})
    if node == "prediction":
        fr = update.get("forecast_result", {})
        return (f"Forecasted next {update.get('forecast_horizon_minutes', 60)} min: "
                f"building load {fr.get('building_load_forecast_kw')} kW, peak risk "
                f"{update.get('peak_risk', {}).get('level')}.",
                {"confidence": update.get("forecast_confidence"),
                 "high_comfort_risk_zones": fr.get("high_comfort_risk_zones", [])})
    if node == "control":
        return (f"Generated {len(update.get('candidate_actions', []))} candidate "
                f"action(s); selected {len(update.get('selected_actions', []))} "
                f"for simulation.",
                {"top_action": (update.get("ranked_actions") or [{}])[0].get("action_type")})
    if node == "simulation":
        sim = update.get("simulation_result", {})
        return (f"Simulated plan: saving {sim.get('expected_saving_kwh', 0)} kWh/day, "
                f"peak -{sim.get('expected_peak_reduction_kw', 0)} kW.",
                {"engine": sim.get("engine")})
    if node == "policy":
        decisions = [d["decision"] for d in update.get("policy_decisions", [])]
        return (f"Policy decisions: {', '.join(decisions) or 'none'}.",
                {"approval_required": update.get("approval_required")})
    if node == "execution":
        ex = update.get("execution_result", {})
        return (f"Executed {len(ex.get('executed', []))} auto action(s); "
                f"{len(ex.get('pending_approval', []))} queued for approval; "
                f"{len(ex.get('rejected', []))} rejected.", {})
    if node == "compare":
        kpi = update.get("baseline_vs_optimized", {})
        return (f"Compared baseline vs optimized: saving "
                f"{kpi.get('saving_kwh', kpi.get('saving_percent', 0))} kWh.", {})
    if node == "report":
        return (f"Report rendered to PDF ({update.get('report_type')}).",
                {"pdf_path": update.get("pdf_path")})
    return ("Step completed.", {})


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def input_router(state: GreenFlowState) -> dict:
    t0 = time.time()
    entrypoint = state.get("entrypoint", "chatbot")
    log = _log_step(state, 0, "input_router", "completed",
                    f"Received {entrypoint} request.", int((time.time() - t0) * 1000))
    return {"agent_logs": state.get("agent_logs", []) + [log]}


def intent_classifier(state: GreenFlowState) -> dict:
    t0 = time.time()
    update = intent.run(state)
    log = _log_step(state, 1, "intent_classifier", "completed",
                    f"Intent: {update.get('intent')}.",
                    int((time.time() - t0) * 1000),
                    {"intent": update.get("intent"),
                     "resolved_zones": update.get("selected_zone_ids", [])})
    update["agent_logs"] = state.get("agent_logs", []) + [log]
    return update


def orchestration_planner(state: GreenFlowState) -> dict:
    t0 = time.time()
    update = planner.run(state)
    steps = [s["node"] for s in update["orchestration_plan"]]
    log = _log_step(state, 2, "orchestration_planner", "completed",
                    f"Plan: {' -> '.join(NODE_LABELS.get(s, s) for s in steps)}.",
                    int((time.time() - t0) * 1000), {"steps": steps})
    update["agent_logs"] = state.get("agent_logs", []) + [log]
    return update


def plan_executor(state: GreenFlowState) -> dict:
    merged: dict = {}
    working = dict(state)
    logs = list(state.get("agent_logs", []))
    errors = list(state.get("errors", []))
    base_step = 3

    for i, plan_item in enumerate(state.get("orchestration_plan", [])):
        node_name = plan_item["node"]
        fn = PLAN_NODES.get(node_name)
        if fn is None:
            continue
        t0 = time.time()
        try:
            update = fn(working)  # type: ignore[arg-type]
            message, summary = _summarize(node_name, update)
            status = "completed"
        except Exception as exc:  # keep the run alive; report the failure
            update = {}
            message, summary = f"{NODE_LABELS.get(node_name, node_name)} failed: {exc}", {}
            status = "failed"
            errors.append({"node": node_name, "error": str(exc)})
        duration = int((time.time() - t0) * 1000)
        logs.append(_log_step(working, base_step + i, node_name, status,
                              message, duration, summary))
        working.update(update)
        merged.update(update)

    merged["agent_logs"] = logs
    merged["errors"] = errors
    merged["current_plan_step"] = len(state.get("orchestration_plan", []))
    return merged


def response_composer(state: GreenFlowState) -> dict:
    t0 = time.time()
    update = composer.compose(state)
    log = _log_step(state, 90, "response_composer", "completed",
                    "Composed final answer, dashboard cards and viewer updates.",
                    int((time.time() - t0) * 1000),
                    {"cards": len(update.get("dashboard_cards", [])),
                     "viewer_updates": len(update.get("viewer_updates", []))})
    update["agent_logs"] = state.get("agent_logs", []) + [log]
    return update


def audit_logger(state: GreenFlowState) -> dict:
    t0 = time.time()
    composer.audit(state)
    log = _log_step(state, 99, "audit_logger", "completed",
                    "Audit log saved.", int((time.time() - t0) * 1000))
    return {"agent_logs": state.get("agent_logs", []) + [log]}


def build_graph():
    g = StateGraph(GreenFlowState)
    g.add_node("input_router", input_router)
    g.add_node("intent_classifier", intent_classifier)
    g.add_node("orchestration_planner", orchestration_planner)
    g.add_node("plan_executor", plan_executor)
    g.add_node("response_composer", response_composer)
    g.add_node("audit_logger", audit_logger)

    g.add_edge(START, "input_router")
    g.add_edge("input_router", "intent_classifier")
    g.add_edge("intent_classifier", "orchestration_planner")
    g.add_edge("orchestration_planner", "plan_executor")
    g.add_edge("plan_executor", "response_composer")
    g.add_edge("response_composer", "audit_logger")
    g.add_edge("audit_logger", END)
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph

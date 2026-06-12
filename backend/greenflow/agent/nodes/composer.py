"""Response Composer + Audit Logger: final answer, dashboard cards, viewer updates."""

from __future__ import annotations

import json

from sqlalchemy import text

from ...db import db_conn
from ..llm import llm_text
from ..state import GreenFlowState

SEVERITY_COLORS = {"high": "#DC2626", "watch": "#F59E0B", "info": "#2563EB"}


def compose(state: GreenFlowState) -> dict:
    intent = state.get("intent") or ""
    cards: list[dict] = []
    viewer_updates: list[dict] = []
    related: list[dict] = []

    sim = state.get("simulation_result", {})
    if sim.get("expected_saving_kwh") is not None:
        cards.append({"title": "Expected Saving",
                      "value": f"{sim['expected_saving_kwh']} kWh",
                      "subtitle": f"{sim.get('expected_cost_saving_vnd', 0):,.0f} VND/day",
                      "status": "success"})
        cards.append({"title": "Peak Reduction",
                      "value": f"{sim.get('expected_peak_reduction_kw', 0)} kW",
                      "subtitle": "13:00-16:00 window", "status": "success"})
        comfort_delta = sim.get("comfort_violation_delta_min", 0)
        cards.append({"title": "Comfort Impact",
                      "value": f"{comfort_delta:+d} min",
                      "subtitle": "violation delta vs baseline",
                      "status": "success" if comfort_delta <= 0 else "warning"})

    exec_result = state.get("execution_result", {})
    if exec_result:
        cards.append({"title": "Actions",
                      "value": f"{len(exec_result.get('executed', []))} auto / "
                               f"{len(exec_result.get('pending_approval', []))} pending",
                      "subtitle": f"{len(exec_result.get('rejected', []))} blocked by policy",
                      "status": "info"})

    for f in state.get("abnormal_findings", []):
        if f.get("zone_key"):
            viewer_updates.append({
                "entity_id": f["zone_key"],
                "style": {"color": SEVERITY_COLORS.get(f["severity"], "#F59E0B"),
                          "outline": True,
                          "label": f["finding_type"].replace("_", " ")},
            })
            related.append({"entity_key": f["zone_key"], "entity_type": "ThermalZone",
                            "label": f.get("zone_name", f["zone_key"])})
    for a in state.get("final_action_plan", []):
        for zk in a.get("target_zone_keys", []):
            viewer_updates.append({"entity_id": zk,
                                   "style": {"color": "#0F766E", "outline": True,
                                             "label": a["action_type"].replace("_", " ")}})

    answer = _fallback_answer(state)
    if state.get("entrypoint") == "chatbot":
        answer = llm_text(
            "You are GreenFlow, a building operations copilot. Using the data below, "
            f"answer the user's question concisely with numbers.\n"
            f"Question: {state.get('user_query')}\n"
            f"Data: {json.dumps(_answer_context(state), default=str)[:6000]}",
            answer)

    suggested = []
    if state.get("abnormal_findings"):
        suggested.append("run_optimization")
    if sim:
        suggested.append("compare_baseline_optimized")
    if not suggested:
        suggested = ["building_semantic_report"]

    return {
        "final_answer": answer,
        "dashboard_cards": cards,
        "viewer_updates": _dedupe(viewer_updates),
        "related_entities": _dedupe_by(related, "entity_key"),
        "suggested_buttons": suggested,
    }


def audit(state: GreenFlowState) -> dict:
    with db_conn() as conn:
        conn.execute(text("""
            INSERT INTO audit_logs (actor_type, actor_id, action_type, entity_type,
                                    entity_id, payload_json)
            VALUES ('agent', 'orchestrator', :at, 'agent_run', :rid, cast(:p as jsonb))
        """), {"at": f"run_{state.get('intent') or 'unknown'}",
               "rid": state.get("run_id", ""),
               "p": json.dumps({
                   "entrypoint": state.get("entrypoint"),
                   "intent": state.get("intent"),
                   "findings": len(state.get("abnormal_findings", [])),
                   "actions": [a.get("action_type")
                               for a in state.get("final_action_plan", [])],
                   "approval_required": state.get("approval_required", False),
                   "report_id": state.get("report_id"),
               }, default=str)})
    return {}


def _answer_context(state: GreenFlowState) -> dict:
    return {
        "semantic_context": state.get("semantic_context"),
        "abnormal_findings": state.get("abnormal_findings"),
        "latest_zone_state": state.get("latest_zone_state"),
        "forecast": state.get("forecast_result"),
        "comfort_risk": state.get("comfort_risk"),
        "peak_risk": state.get("peak_risk"),
        "simulation": state.get("simulation_result"),
        "final_action_plan": state.get("final_action_plan"),
    }


def _fallback_answer(state: GreenFlowState) -> str:
    intent = state.get("intent") or ""
    parts: list[str] = []

    findings = state.get("abnormal_findings", [])
    sim = state.get("simulation_result", {})
    plan = state.get("final_action_plan", [])

    if intent in ("semantic_query", "hvac_elec_query", "general_help") or not intent:
        sc = state.get("semantic_context", {})
        if sc:
            parts.append(
                f"{sc.get('building_name', 'The building')} has {sc.get('zone_count')} "
                f"zones across {sc.get('floor_count')} floor(s) with "
                f"{sc.get('device_count')} mapped devices.")
    if findings:
        top = findings[:3]
        parts.append(f"{len(findings)} finding(s) need attention: " +
                     "; ".join(f["detail"] for f in top) + ".")
    elif intent in ("semantic_query", "energy_query", "comfort_query"):
        parts.append("No abnormal behavior detected at the latest tick.")

    fr = state.get("forecast_result", {})
    if fr:
        parts.append(
            f"Forecast ({state.get('forecast_horizon_minutes', 60)} min): building load "
            f"{fr.get('building_load_now_kw')} -> {fr.get('building_load_forecast_kw')} kW, "
            f"peak risk {state.get('peak_risk', {}).get('level', 'normal')}, "
            f"confidence {state.get('forecast_confidence', 0):.0%}.")
    if sim.get("expected_saving_kwh") is not None:
        parts.append(
            f"Simulated plan saves {sim['expected_saving_kwh']} kWh/day "
            f"({sim.get('expected_cost_saving_vnd', 0):,.0f} VND), cuts peak by "
            f"{sim.get('expected_peak_reduction_kw', 0)} kW with "
            f"{sim.get('comfort_violation_delta_min', 0):+d} min comfort delta.")
    if plan:
        auto = sum(1 for a in plan if a["policy_decision"] == "auto_run")
        pend = sum(1 for a in plan if a["policy_decision"] == "approval_required")
        rej = len(plan) - auto - pend
        parts.append(f"Action plan: {auto} auto-executed, {pend} awaiting approval, "
                     f"{rej} rejected by policy.")
    if state.get("pdf_path"):
        parts.append("Report PDF is ready for download.")
    return " ".join(parts) or "Done."


def _dedupe(updates: list[dict]) -> list[dict]:
    seen = {}
    for u in updates:
        seen[u["entity_id"]] = u
    return list(seen.values())


def _dedupe_by(items: list[dict], key: str) -> list[dict]:
    seen = {}
    for i in items:
        seen[i[key]] = i
    return list(seen.values())

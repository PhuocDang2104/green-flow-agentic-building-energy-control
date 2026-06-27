"""Agent service: create runs, execute the graph, expose run status/logs."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import text

from ..db import db_conn, fetch_all, fetch_one
from .state import new_state
from .tools.db_tool import _clean


def start_run(building_id: str, entrypoint: str, *,
              button_action: str | None = None,
              user_query: str | None = None,
              scenario_config: dict | None = None,
              session_id: str | None = None) -> str:
    """Insert the agent_runs row and return run_id (execution happens in
    execute_run, typically on a background thread)."""
    run_id = str(uuid.uuid4())
    with db_conn() as conn:
        conn.execute(text("""
            INSERT INTO agent_runs (id, building_id, entrypoint, button_action,
                                    user_query, status, scenario_config)
            VALUES (:id, :b, :e, :ba, :q, 'running', cast(:sc as jsonb))
        """), {"id": run_id, "b": building_id, "e": entrypoint, "ba": button_action,
               "q": user_query, "sc": json.dumps(scenario_config or {})})
        if session_id:
            # Persist the run as a chat event in the same transaction as the
            # run row. The frontend can therefore restore every inline trace
            # from chat history after a reload.
            action = button_action or "agent_run"
            label = action.replace("_", " ").title()
            tool_call = {
                "name": "trigger_agent_action",
                "args": {"action": action},
                "result": {"run_id": run_id, "status": "running", "action": action},
            }
            conn.execute(text("""
                INSERT INTO chat_messages (session_id, role, content, tool_calls)
                VALUES (:session, 'assistant', :content, cast(:tools as jsonb))
            """), {
                "session": session_id,
                "content": f"Started **{label}**.",
                "tools": json.dumps([tool_call]),
            })
    return run_id


def execute_run(run_id: str, building_id: str, entrypoint: str, *,
                button_action: str | None = None,
                user_query: str | None = None,
                scenario_config: dict | None = None,
                session_id: str | None = None) -> dict:
    state = new_state(
        request_id=run_id, run_id=run_id, building_id=building_id,
        entrypoint=entrypoint, button_action=button_action, user_query=user_query,
        scenario_config=scenario_config or {}, session_id=session_id or run_id,
        user_id="demo",
    )
    try:
        from .graph import get_graph
        final = get_graph().invoke(state)
        status = "awaiting_approval" if final.get("approval_required") else "completed"
        _finish_run(run_id, status, final)
        return final
    except Exception as exc:
        _finish_run(run_id, "failed", {"final_answer": f"Run failed: {exc}"})
        raise


def _finish_run(run_id: str, status: str, final: dict) -> None:
    persistable = {
        "intent": final.get("intent"),
        "abnormal_findings": final.get("abnormal_findings", []),
        "forecast_result": final.get("forecast_result", {}),
        "comfort_risk": final.get("comfort_risk", {}),
        "peak_risk": final.get("peak_risk", {}),
        "forecast_confidence": final.get("forecast_confidence"),
        "prediction_explanation": final.get("prediction_explanation", {}),
        "candidate_actions": final.get("candidate_actions", []),
        "final_action_plan": final.get("final_action_plan", []),
        "policy_decisions": final.get("policy_decisions", []),
        "simulation_result": final.get("simulation_result", {}),
        "baseline_vs_optimized": final.get("baseline_vs_optimized", {}),
        "execution_result": final.get("execution_result", {}),
        "report_id": final.get("report_id"),
        "pdf_path": final.get("pdf_path"),
        "related_entities": final.get("related_entities", []),
        "suggested_buttons": final.get("suggested_buttons", []),
        "errors": final.get("errors", []),
        "stop_reason": final.get("stop_reason"),
        "degraded_nodes": final.get("degraded_nodes", []),
    }
    with db_conn() as conn:
        conn.execute(text("""
            UPDATE agent_runs
            SET status = :s, finished_at = now(), intent = :i, final_answer = :fa,
                dashboard_cards = cast(:dc as jsonb),
                viewer_updates = cast(:vu as jsonb),
                state_json = cast(:st as jsonb)
            WHERE id = :id
        """), {"id": run_id, "s": status, "i": final.get("intent"),
               "fa": final.get("final_answer", ""),
               "dc": json.dumps(final.get("dashboard_cards", []), default=str),
               "vu": json.dumps(final.get("viewer_updates", []), default=str),
               "st": json.dumps(persistable, default=str)})


def get_run(run_id: str) -> dict | None:
    with db_conn() as conn:
        run = fetch_one(conn, "SELECT * FROM agent_runs WHERE id = :id", id=run_id)
        return _clean(run) if run else None


def get_run_logs(run_id: str) -> list[dict]:
    with db_conn() as conn:
        return [_clean(r) for r in fetch_all(conn, """
            SELECT step, node, status, message, duration_ms, output_summary, created_at
            FROM agent_logs WHERE run_id = :r ORDER BY step, created_at
        """, r=run_id)]


def resolve_approval(approval_id: str, decision: str, decided_by: str = "demo_user",
                     note: str = "") -> dict:
    """Approve/reject a pending action (approval_resume entrypoint)."""
    assert decision in ("approved", "rejected")
    with db_conn() as conn:
        approval = fetch_one(conn, """
            SELECT a.*, ar.action_id FROM approval_requests ar
            JOIN actions a ON a.id = ar.action_id
            WHERE ar.id = :id
        """, id=approval_id)
        if not approval:
            return {"error": "approval not found"}
        conn.execute(text("""
            UPDATE approval_requests SET status = :s, decided_at = now(),
                   decided_by = :by, decision_note = :note WHERE id = :id
        """), {"id": approval_id, "s": decision, "by": decided_by, "note": note})
        new_status = "executed" if decision == "approved" else "rejected"
        conn.execute(text("UPDATE actions SET status = :s WHERE id = :a"),
                     {"s": new_status, "a": approval["action_id"]})
        conn.execute(text("""
            INSERT INTO audit_logs (actor_type, actor_id, action_type, entity_type,
                                    entity_id, payload_json)
            VALUES ('human', :by, :at, 'action', :eid, cast(:p as jsonb))
        """), {"by": decided_by,
               "at": f"approval_{decision}",
               "eid": str(approval["action_id"]),
               "p": json.dumps({"approval_id": approval_id, "note": note})})
    return {"approval_id": approval_id, "decision": decision,
            "action_status": new_status,
            "note": "Mock execution: no real BMS command sent." if decision == "approved"
            else note}

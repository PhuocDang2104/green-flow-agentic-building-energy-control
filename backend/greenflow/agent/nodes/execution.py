"""Execution node: mock-execute auto actions, queue approvals, log rejections.

Persists actions / action_targets / approval_requests / audit_logs. Execution
is a mock state change (this layer sits above a BMS; REPO_BUILD_SPEC §0).
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import text

from ...db import db_conn, fetch_all
from ..state import GreenFlowState

STATUS_BY_DECISION = {
    "auto_run": "executed",
    "approval_required": "pending_approval",
    "rejected": "blocked",
}


def run(state: GreenFlowState) -> dict:
    building_id = state["building_id"]
    run_id = state.get("run_id")
    sim = state.get("simulation_result", {})
    executed, pending, rejected = [], [], []
    approval_requests = []

    with db_conn() as conn:
        zone_ids = {z["entity_key"]: z["id"] for z in fetch_all(
            conn, "SELECT id, entity_key FROM zones WHERE building_id = :b",
            b=building_id)}

        for item in state.get("final_action_plan", []):
            decision = item["policy_decision"]
            status = STATUS_BY_DECISION.get(decision, "proposed")
            action_id = uuid.uuid4()
            conn.execute(text("""
                INSERT INTO actions (id, building_id, agent_run_id, decision_mode,
                    action_type, status, reason, confidence, expected_saving_kwh,
                    expected_peak_reduction_kw, comfort_risk_after, policy_decision,
                    policy_reasons, parameters_json, created_by, simulation_run_id)
                VALUES (:id, :b, :run, :mode, :at, :status, :reason, :conf, :saving,
                        :peak, :comfort, :pd, cast(:pr as jsonb), cast(:params as jsonb),
                        'orchestrator', :sim_run)
            """), {
                "id": action_id, "b": building_id, "run": run_id,
                "mode": "auto" if decision == "auto_run" else "recommendation",
                "at": item["action_type"], "status": status,
                "reason": item.get("reason", ""),
                "conf": state.get("forecast_confidence", 0.8),
                "saving": item.get("expected_saving_kwh"),
                "peak": item.get("expected_peak_reduction_kw"),
                "comfort": sim.get("comfort_risk_after"),
                "pd": decision, "pr": json.dumps(item.get("policy_reasons", [])),
                "params": json.dumps({k: item.get(k) for k in
                                      ("start_hour", "end_hour", "lighting_factor",
                                       "setpoint_delta_c", "hvac_off")}),
                "sim_run": sim.get("optimized_run_id"),
            })
            for zk in item.get("target_zone_keys", []):
                zid = zone_ids.get(zk)
                if zid:
                    conn.execute(text("""
                        INSERT INTO action_targets (action_id, target_type, target_id,
                                                    parameters_json)
                        VALUES (:a, 'zone', :t, cast(:p as jsonb))
                    """), {"a": action_id, "t": zid, "p": json.dumps({"zone_key": zk})})

            record = {**item, "action_id": str(action_id), "status": status}
            if decision == "auto_run":
                executed.append(record)
                _audit(conn, "agent", "action_executed", "action", str(action_id), {
                    "action_type": item["action_type"],
                    "targets": item.get("target_zone_keys", []),
                    "mode": "mock_execution",
                })
            elif decision == "approval_required":
                approval_id = uuid.uuid4()
                conn.execute(text("""
                    INSERT INTO approval_requests (id, action_id, building_id, status,
                                                   payload_json)
                    VALUES (:id, :a, :b, 'pending', cast(:p as jsonb))
                """), {"id": approval_id, "a": action_id, "b": building_id,
                       "p": json.dumps(record)})
                record["approval_id"] = str(approval_id)
                pending.append(record)
                approval_requests.append(record)
                _audit(conn, "agent", "approval_requested", "action", str(action_id),
                       {"action_type": item["action_type"]})
            else:
                rejected.append(record)
                _audit(conn, "agent", "action_rejected", "action", str(action_id),
                       {"action_type": item["action_type"],
                        "reasons": item.get("policy_reasons", [])})

    return {
        "execution_result": {
            "executed": executed, "pending_approval": pending, "rejected": rejected,
            "note": "Mock execution: state recorded in DB, no real BMS command sent.",
        },
        "approval_requests": approval_requests,
    }


def _audit(conn, actor: str, action_type: str, entity_type: str, entity_id: str,
           payload: dict) -> None:
    conn.execute(text("""
        INSERT INTO audit_logs (actor_type, actor_id, action_type, entity_type,
                                entity_id, payload_json)
        VALUES ('agent', :actor, :at, :et, :eid, cast(:p as jsonb))
    """), {"actor": actor, "at": action_type, "et": entity_type, "eid": entity_id,
           "p": json.dumps(payload)})

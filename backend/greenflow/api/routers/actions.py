"""Action queue, approvals and audit log APIs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ...agent import service
from ...agent.tools.db_tool import _clean
from ...db import db_conn, fetch_all, fetch_one
from ..deps import default_building_id

router = APIRouter()


@router.get("/actions")
def list_actions(building_id: str = Query(default=None),
                 status: str | None = None, limit: int = 200):
    with db_conn() as conn:
        sql = """
            SELECT a.*,
                   coalesce(json_agg(json_build_object(
                       'target_type', t.target_type, 'target_id', t.target_id,
                       'parameters', t.parameters_json))
                     FILTER (WHERE t.id IS NOT NULL), '[]') AS targets
            FROM actions a
            LEFT JOIN action_targets t ON t.action_id = a.id
            WHERE a.building_id = :b
        """
        params: dict = {"b": building_id or default_building_id(), "lim": limit}
        if status:
            sql += " AND a.status = :status"
            params["status"] = status
        sql += " GROUP BY a.id ORDER BY a.requested_at DESC LIMIT :lim"
        return [_clean(r) for r in fetch_all(conn, sql, **params)]


@router.get("/actions/{action_id}")
def get_action(action_id: str):
    with db_conn() as conn:
        row = fetch_one(conn, "SELECT * FROM actions WHERE id = :a", a=action_id)
    if not row:
        raise HTTPException(404, "action not found")
    return _clean(row)


@router.get("/approvals")
def list_approvals(building_id: str = Query(default=None),
                   status: str = "pending"):
    with db_conn() as conn:
        return [_clean(r) for r in fetch_all(conn, """
            SELECT ar.id AS approval_id, ar.status, ar.requested_at, ar.decided_at,
                   ar.decided_by, ar.payload_json,
                   a.id AS action_id, a.action_type, a.reason,
                   a.expected_saving_kwh, a.expected_peak_reduction_kw,
                   a.comfort_risk_after, a.policy_reasons
            FROM approval_requests ar JOIN actions a ON a.id = ar.action_id
            WHERE ar.building_id = :b AND (:status = 'all' OR ar.status = :status)
            ORDER BY ar.requested_at DESC
        """, b=building_id or default_building_id(), status=status)]


class DecisionRequest(BaseModel):
    decided_by: str = "demo_user"
    note: str = ""


@router.post("/approvals/{approval_id}/approve")
def approve(approval_id: str, req: DecisionRequest):
    result = service.resolve_approval(approval_id, "approved", req.decided_by, req.note)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/approvals/{approval_id}/reject")
def reject(approval_id: str, req: DecisionRequest):
    result = service.resolve_approval(approval_id, "rejected", req.decided_by, req.note)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.get("/audit-log")
def audit_log(limit: int = 100):
    with db_conn() as conn:
        return [_clean(r) for r in fetch_all(conn, """
            SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT :lim
        """, lim=limit)]


@router.get("/policy-config")
def policy_config():
    from ...agent.policy import load_policy
    return load_policy()

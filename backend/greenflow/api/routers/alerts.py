"""Alerts API — Fault Detection & Diagnostics (FDD) surface.

Lists the alerts written by the anomaly engine (agent/anomaly.py) with zone/device
names + severity ordering, and lets an operator acknowledge (resolve) one.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ...agent.tools.db_tool import _clean
from ...db import db_conn, fetch_all, fetch_one
from ..deps import default_building_id

router = APIRouter()


@router.get("/alerts")
def list_alerts(building_id: str = Query(default=None), status: str = "open",
                limit: int = 100):
    """status: open (resolved_at NULL) | resolved | all. Sorted critical-first."""
    b = building_id or default_building_id()
    cond = ("a.resolved_at IS NULL" if status == "open"
            else "a.resolved_at IS NOT NULL" if status == "resolved" else "TRUE")
    with db_conn() as conn:
        rows = [_clean(r) for r in fetch_all(conn, f"""
            SELECT a.id, a.alert_type, a.severity, a.message, a.created_at, a.resolved_at,
                   z.entity_key AS zone_key, z.name AS zone_name, z.room_type,
                   d.name AS device_name
            FROM alerts a
            LEFT JOIN zones z ON z.id = a.zone_id
            LEFT JOIN devices d ON d.id = a.device_id
            WHERE a.building_id = :b AND {cond}
            ORDER BY CASE a.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                     a.created_at DESC
            LIMIT :lim
        """, b=b, lim=limit)]
    return rows


@router.get("/alerts/summary")
def alerts_summary(building_id: str = Query(default=None)):
    b = building_id or default_building_id()
    with db_conn() as conn:
        rows = fetch_all(conn, """
            SELECT severity, count(*) AS n FROM alerts
            WHERE building_id = :b AND resolved_at IS NULL GROUP BY severity
        """, b=b)
    out = {"critical": 0, "warning": 0, "info": 0, "total": 0}
    for r in rows:
        out[r["severity"]] = r["n"]
        out["total"] += r["n"]
    return out


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: str):
    with db_conn() as conn:
        row = fetch_one(conn, """
            UPDATE alerts SET resolved_at = now()
            WHERE id = :i AND resolved_at IS NULL RETURNING id""", i=alert_id)
    if not row:
        raise HTTPException(404, "alert not found or already resolved")
    return {"id": alert_id, "resolved": True}

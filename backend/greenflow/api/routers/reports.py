"""Report listing and metadata (files served from /storage static mount)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ...agent.tools.db_tool import _clean
from ...db import db_conn, fetch_all, fetch_one
from ..deps import default_building_id

router = APIRouter()


@router.get("/reports")
def list_reports(building_id: str = Query(default=None), limit: int = 20):
    with db_conn() as conn:
        rows = [_clean(r) for r in fetch_all(conn, """
            SELECT * FROM reports WHERE building_id = :b
            ORDER BY created_at DESC LIMIT :lim
        """, b=building_id or default_building_id(), lim=limit)]
    for r in rows:
        r["pdf_url"] = f"/storage/{r['pdf_path']}" if r.get("pdf_path") else None
    return rows


@router.get("/reports/{report_id}")
def get_report(report_id: str):
    with db_conn() as conn:
        row = fetch_one(conn, "SELECT * FROM reports WHERE id = :r", r=report_id)
    if not row:
        raise HTTPException(404, "report not found")
    out = _clean(row)
    out["pdf_url"] = f"/storage/{out['pdf_path']}" if out.get("pdf_path") else None
    return out

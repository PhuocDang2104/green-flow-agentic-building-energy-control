"""Report listing and metadata (PDF in MinIO via /media; legacy via /storage)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ...agent.tools.db_tool import _clean
from ...db import db_conn, fetch_all, fetch_one
from ..deps import default_building_id

router = APIRouter()


def _file_url(path: str | None) -> str | None:
    """Build a browser URL from a stored path: object keys -> /media proxy,
    legacy storage-relative paths -> /storage static mount."""
    if not path:
        return None
    return f"/storage/{path}" if path.startswith("processed/") else f"/media/{path}"


@router.get("/reports")
def list_reports(building_id: str = Query(default=None), limit: int = 20):
    with db_conn() as conn:
        rows = [_clean(r) for r in fetch_all(conn, """
            SELECT * FROM reports WHERE building_id = :b
            ORDER BY created_at DESC LIMIT :lim
        """, b=building_id or default_building_id(), lim=limit)]
    for r in rows:
        r["pdf_url"] = _file_url(r.get("pdf_path"))
    return rows


@router.get("/reports/{report_id}")
def get_report(report_id: str):
    with db_conn() as conn:
        row = fetch_one(conn, "SELECT * FROM reports WHERE id = :r", r=report_id)
    if not row:
        raise HTTPException(404, "report not found")
    out = _clean(row)
    out["pdf_url"] = _file_url(out.get("pdf_path"))
    return out

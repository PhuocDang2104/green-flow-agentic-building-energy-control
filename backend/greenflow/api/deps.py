"""Shared API helpers: id resolution and error shortcuts."""

from __future__ import annotations

import uuid

from fastapi import HTTPException

from ..config import get_settings
from ..db import db_conn, fetch_one


def default_building_id() -> str:
    return get_settings().default_building_id


def resolve_zone(zone_ref: str, building_id: str | None = None) -> dict:
    """Accept a zone UUID or entity_key and return the zone row."""
    with db_conn() as conn:
        if _is_uuid(zone_ref):
            row = fetch_one(conn, "SELECT * FROM zones WHERE id = :z", z=zone_ref)
        else:
            row = fetch_one(conn, """
                SELECT * FROM zones WHERE entity_key = :z
                AND (:b IS NULL OR building_id = cast(:b as uuid)) LIMIT 1
            """, z=zone_ref, b=building_id)
    if not row:
        raise HTTPException(404, f"zone '{zone_ref}' not found")
    return row


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False

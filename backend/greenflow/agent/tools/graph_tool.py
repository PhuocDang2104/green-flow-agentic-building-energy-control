"""Semantic graph queries over entity_relations (recursive CTE, no Neo4j)."""

from __future__ import annotations

from ...db import db_conn, fetch_all
from .db_tool import _clean


def get_neighbors(building_id: str, entity_id: str) -> list[dict]:
    """Direct relations (both directions) of an entity."""
    with db_conn() as conn:
        return [_clean(r) for r in fetch_all(conn, """
            SELECT relation_type, src_entity_type, src_entity_id,
                   dst_entity_type, dst_entity_id, confidence, method
            FROM entity_relations
            WHERE building_id = :b AND (src_entity_id = :e OR dst_entity_id = :e)
        """, b=building_id, e=entity_id)]


def get_zone_equipment_map(building_id: str) -> dict[str, list[dict]]:
    """zone entity_key -> devices located in / supplying that zone."""
    with db_conn() as conn:
        rows = fetch_all(conn, """
            SELECT z.entity_key AS zone_key, d.entity_key AS device_key, d.name,
                   d.device_type, d.device_subtype, d.controllable, r.relation_type
            FROM entity_relations r
            JOIN devices d ON d.id = r.src_entity_id
            JOIN zones z ON z.id = r.dst_entity_id
            WHERE r.building_id = :b
              AND r.relation_type IN ('LOCATED_IN', 'SUPPLIES_AIR_TO')
        """, b=building_id)
    out: dict[str, list[dict]] = {}
    seen: set[tuple[str, str]] = set()
    for r in rows:
        key = (r["zone_key"], r["device_key"])
        if key in seen:
            continue
        seen.add(key)
        out.setdefault(r["zone_key"], []).append(_clean(r))
    return out


def get_missing_metadata(building_id: str) -> list[dict]:
    """Quality checks: devices without zone, zones without devices, etc."""
    findings: list[dict] = []
    with db_conn() as conn:
        unmapped = fetch_all(conn, """
            SELECT entity_key, name, device_type FROM devices
            WHERE building_id = :b AND zone_id IS NULL
              AND device_subtype NOT IN ('ahu', 'distribution_board')
        """, b=building_id)
        for d in unmapped:
            findings.append({"type": "device_without_zone", "entity_key": d["entity_key"],
                             "detail": f"{d['name']} has no zone mapping"})
        no_devices = fetch_all(conn, """
            SELECT z.entity_key, z.name FROM zones z
            WHERE z.building_id = :b
              AND NOT EXISTS (SELECT 1 FROM devices d WHERE d.zone_id = z.id)
        """, b=building_id)
        for z in no_devices:
            findings.append({"type": "zone_without_devices", "entity_key": z["entity_key"],
                             "detail": f"{z['name']} has no mapped devices"})
        no_mesh = fetch_all(conn, """
            SELECT z.entity_key, z.name FROM zones z
            WHERE z.building_id = :b
              AND NOT EXISTS (SELECT 1 FROM mesh_entity_map m
                              WHERE m.building_id = :b AND m.entity_key = z.entity_key)
        """, b=building_id)
        for z in no_mesh:
            findings.append({"type": "zone_without_3d_object", "entity_key": z["entity_key"],
                             "detail": f"{z['name']} has no 3D mesh mapping"})
    return findings

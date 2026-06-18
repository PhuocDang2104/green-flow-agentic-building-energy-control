"""Entity inspection APIs: metadata, latest state, graph neighbors.

entity_ref is an entity_key (zone_*, airterminal_*, lighting_*, ...) — the
same stable id used by the 3D viewer objects.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ...agent.tools import db_tool, graph_tool, timeseries_tool
from ...agent.tools.db_tool import _clean
from ...db import db_conn, fetch_all, fetch_one
from ..deps import default_building_id

router = APIRouter()


def _find_entity(building_id: str, entity_ref: str) -> tuple[str, dict] | None:
    with db_conn() as conn:
        zone = fetch_one(conn, """
            SELECT * FROM zones WHERE building_id = :b AND entity_key = :k
        """, b=building_id, k=entity_ref)
        if zone:
            return "ThermalZone", _clean(zone)
        device = fetch_one(conn, """
            SELECT d.*, z.entity_key AS zone_key, z.name AS zone_name
            FROM devices d LEFT JOIN zones z ON z.id = d.zone_id
            WHERE d.building_id = :b AND d.entity_key = :k
        """, b=building_id, k=entity_ref)
        if device:
            return "Device", _clean(device)
        mesh = fetch_one(conn, """
            SELECT * FROM mesh_entity_map WHERE building_id = :b AND mesh_id = :k
        """, b=building_id, k=entity_ref)
        if mesh:
            return mesh["entity_type"], _clean(mesh)
    return None


@router.get("/entities/{entity_ref}")
def get_entity(entity_ref: str, building_id: str = Query(default=None)):
    b = building_id or default_building_id()
    found = _find_entity(b, entity_ref)
    if not found:
        raise HTTPException(404, f"entity '{entity_ref}' not found")
    entity_type, data = found
    result = {"entity_type": entity_type, "entity_key": entity_ref, **data}

    # Non-curated IFC spaces resolve via mesh_entity_map (no DB zone row).
    # Surface their enriched name/room_type so the inspector isn't blank.
    props = data.get("properties") or {}
    if entity_type == "ThermalZone" and not data.get("id"):
        result["name"] = props.get("name") or result.get("name")
        result["room_type"] = props.get("room_type")
        result["live"] = props.get("live", False)
        result["devices"] = []
        result["latest_state"] = None
        return result

    if entity_type == "ThermalZone":
        result["devices"] = db_tool.get_devices(b, data["id"])
        result["cameras"] = db_tool.get_cameras(b, data["id"])
        state = db_tool.get_latest_zone_state(b)
        result["latest_state"] = state.get(entity_ref)
    elif entity_type == "Device":
        state = db_tool.get_latest_device_state(b)
        result["latest_state"] = state.get(entity_ref)
    return result


@router.get("/entities/{entity_ref}/state")
def entity_state(entity_ref: str, building_id: str = Query(default=None),
                 hours: int = 24):
    b = building_id or default_building_id()
    found = _find_entity(b, entity_ref)
    if not found:
        raise HTTPException(404, f"entity '{entity_ref}' not found")
    entity_type, data = found
    if entity_type == "ThermalZone":
        return {"entity_type": entity_type,
                "history": timeseries_tool.get_zone_history(b, data["id"], hours)}
    if entity_type == "Device":
        with db_conn() as conn:
            history = [_clean(r) for r in fetch_all(conn, f"""
                SELECT timestamp, status, setpoint_c, power_kw, energy_kwh
                FROM telemetry_device_15m
                WHERE device_id = :d AND timestamp > now() - interval '{int(hours)} hours'
                ORDER BY timestamp
            """, d=data["id"])]
        return {"entity_type": entity_type, "history": history}
    return {"entity_type": entity_type, "history": []}


@router.get("/entities/{entity_ref}/neighbors")
def entity_neighbors(entity_ref: str, building_id: str = Query(default=None)):
    b = building_id or default_building_id()
    found = _find_entity(b, entity_ref)
    if not found:
        raise HTTPException(404, f"entity '{entity_ref}' not found")
    entity_type, data = found
    entity_id = data.get("id") or data.get("entity_id")
    if not entity_id:
        return {"relations": []}
    relations = graph_tool.get_neighbors(b, str(entity_id))

    # enrich endpoints with names
    with db_conn() as conn:
        names = {str(r["id"]): {"name": r["name"], "entity_key": r["entity_key"],
                                "kind": "zone"}
                 for r in fetch_all(conn,
                                    "SELECT id, name, entity_key FROM zones WHERE building_id = :b",
                                    b=b)}
        names.update({str(r["id"]): {"name": r["name"], "entity_key": r["entity_key"],
                                     "kind": "device"}
                      for r in fetch_all(conn,
                                         "SELECT id, name, entity_key FROM devices WHERE building_id = :b",
                                         b=b)})
    for rel in relations:
        rel["src"] = names.get(str(rel["src_entity_id"]))
        rel["dst"] = names.get(str(rel["dst_entity_id"]))
    return {"entity_key": entity_ref, "entity_type": entity_type,
            "relations": relations}

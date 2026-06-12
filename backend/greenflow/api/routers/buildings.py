"""Building / floor / zone / device read APIs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ...agent.tools import db_tool, graph_tool, timeseries_tool
from ...db import db_conn, fetch_all, fetch_one
from ...agent.tools.db_tool import _clean
from ..deps import default_building_id, resolve_zone

router = APIRouter()


@router.get("/buildings")
def list_buildings():
    with db_conn() as conn:
        return [_clean(r) for r in fetch_all(conn, "SELECT * FROM buildings ORDER BY name")]


@router.get("/buildings/{building_id}")
def get_building(building_id: str):
    with db_conn() as conn:
        row = fetch_one(conn, "SELECT * FROM buildings WHERE id = :b", b=building_id)
    if not row:
        raise HTTPException(404, "building not found")
    return _clean(row)


@router.get("/buildings/{building_id}/summary")
def building_summary(building_id: str):
    return db_tool.get_building_summary(building_id)


@router.get("/buildings/{building_id}/kpis")
def building_kpis(building_id: str):
    return timeseries_tool.get_building_kpis(building_id)


@router.get("/floors")
def list_floors(building_id: str = Query(default=None)):
    return db_tool.get_floors(building_id or default_building_id())


@router.get("/zones")
def list_zones(building_id: str = Query(default=None),
               floor_id: str | None = None):
    b = building_id or default_building_id()
    zones = db_tool.get_zones(b, floor_id)
    state = db_tool.get_latest_zone_state(b)
    for z in zones:
        z["latest_state"] = state.get(z["entity_key"])
    return zones


@router.get("/zones/{zone_ref}")
def get_zone(zone_ref: str):
    zone = _clean(resolve_zone(zone_ref))
    state = db_tool.get_latest_zone_state(zone["building_id"])
    zone["latest_state"] = state.get(zone["entity_key"])
    return zone


@router.get("/zones/{zone_ref}/devices")
def zone_devices(zone_ref: str):
    zone = resolve_zone(zone_ref)
    return db_tool.get_devices(str(zone["building_id"]), str(zone["id"]))


@router.get("/zones/{zone_ref}/state")
def zone_state(zone_ref: str, hours: int = 24):
    zone = resolve_zone(zone_ref)
    return {
        "zone": _clean(zone),
        "history": timeseries_tool.get_zone_history(
            str(zone["building_id"]), str(zone["id"]), hours),
    }


@router.get("/devices")
def list_devices(building_id: str = Query(default=None), zone_id: str | None = None):
    return db_tool.get_devices(building_id or default_building_id(), zone_id)


@router.get("/scenarios")
def list_scenarios(building_id: str = Query(default=None)):
    with db_conn() as conn:
        return [_clean(r) for r in fetch_all(conn, """
            SELECT * FROM scenarios WHERE building_id = :b ORDER BY created_at
        """, b=building_id or default_building_id())]

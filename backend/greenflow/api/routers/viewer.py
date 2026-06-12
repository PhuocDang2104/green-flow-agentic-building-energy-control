"""3D viewer APIs: manifest, assets, object-entity map (DB-backed).

The static XKT/metadata files themselves are served by the web app from
/assets/... ; these endpoints expose the same mapping from the database so
non-web clients (agents, scripts) can resolve viewer object ids to entities.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from ...agent.tools.db_tool import _clean
from ...db import db_conn, fetch_all
from ..deps import default_building_id

router = APIRouter(prefix="/3d")


@router.get("/assets")
def list_assets(building_id: str = Query(default=None)):
    with db_conn() as conn:
        return [_clean(r) for r in fetch_all(conn, """
            SELECT * FROM geometry_assets WHERE building_id = :b ORDER BY layer
        """, b=building_id or default_building_id())]


@router.get("/object-map")
def object_map(building_id: str = Query(default=None), layer: str | None = None):
    with db_conn() as conn:
        sql = """
            SELECT mesh_id, entity_type, entity_id, entity_key, layer
            FROM mesh_entity_map WHERE building_id = :b
        """
        params: dict = {"b": building_id or default_building_id()}
        if layer:
            sql += " AND layer = :layer"
            params["layer"] = layer
        return [_clean(r) for r in fetch_all(conn, sql + " ORDER BY layer, mesh_id",
                                             **params)]


@router.get("/viewer-manifest")
def viewer_manifest(building_id: str = Query(default=None)):
    b = building_id or default_building_id()
    with db_conn() as conn:
        assets = [_clean(r) for r in fetch_all(conn, """
            SELECT layer, asset_url, metadata_url, asset_type, default_visible
            FROM geometry_assets WHERE building_id = :b ORDER BY layer
        """, b=b)]
    return {
        "building_id": b,
        "viewer_stack": "xeokit",
        "geometry_format": "xkt",
        "assets": [{
            "asset_id": a["layer"],
            "layer": a["layer"],
            "model_id": f"model_{a['layer']}",
            "src": a["asset_url"],
            "metadata_src": a["metadata_url"],
            "default_visible": a["default_visible"],
        } for a in assets],
    }

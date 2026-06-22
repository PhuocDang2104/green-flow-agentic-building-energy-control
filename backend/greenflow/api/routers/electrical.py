"""Electrical-distribution + knowledge-graph APIs.

File-backed: serves the artifacts produced by `scripts/build_electrical_kg.py`
(no database required), so it works as soon as the pipeline has run. Board
timeseries are aggregated on demand from Parquet via DuckDB.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ...electrical import canonical as C
from ...electrical import config as cfg
from ...electrical import dashboard
from ...electrical.board_timeseries import BOARD_TS

router = APIRouter()


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _require(path):
    if not path.exists():
        raise HTTPException(503, f"artifact not built: {path.name}. Run scripts/build_electrical_kg.py --all")


@router.get("/electrical/overview")
def overview():
    _require(cfg.OUT_ELEC / "board_annual_summary.csv")
    return dashboard.build_building_overview()


@router.get("/electrical/boards")
def list_boards():
    _require(cfg.OUT_ELEC / "board_annual_summary.csv")
    rows = C.read_rows_csv(cfg.OUT_ELEC / "board_annual_summary.csv")
    return {"count": len(rows), "boards": rows}


@router.get("/electrical/boards/{board_id}")
def board(board_id: str):
    _require(cfg.OUT_ELEC / "electrical_boards.csv")
    v = dashboard.build_board_view(board_id)
    if not v.get("device_tag") and not v.get("estimated", {}).get("total_kwh"):
        raise HTTPException(404, f"board '{board_id}' not found")
    return v


@router.get("/electrical/boards/{board_id}/timeseries")
def board_timeseries(board_id: str, freq: str = Query("daily", pattern="^(daily|monthly|raw)$"),
                     limit: int = 2000):
    _require(BOARD_TS)
    from ...electrical.gold import duckdb_con
    con = duckdb_con()
    p = BOARD_TS.as_posix()
    if freq == "raw":
        q = (f"SELECT timestamp_local, board_lights_kw, board_equipment_kw, board_hvac_kw, "
             f"board_total_kw FROM read_parquet('{p}') WHERE board_id=? ORDER BY timestep_index LIMIT {int(limit)}")
    else:
        trunc = "day" if freq == "daily" else "month"
        q = (f"SELECT date_trunc('{trunc}', timestamp_local) AS bucket, "
             f"avg(board_total_kw) AS avg_kw, max(board_total_kw) AS peak_kw, "
             f"sum(board_total_kwh_interval) AS kwh FROM read_parquet('{p}') "
             f"WHERE board_id=? GROUP BY 1 ORDER BY 1")
    rows = con.execute(q, [board_id]).fetch_arrow_table().to_pylist()
    con.close()
    if not rows:
        raise HTTPException(404, f"no timeseries for board '{board_id}'")
    return {"board_id": board_id, "freq": freq, "points": rows}


@router.get("/electrical/boards/{board_id}/served-zones")
def served_zones(board_id: str):
    _require(cfg.OUT_ELEC / "zone_load_to_board_allocation.csv")
    return {"board_id": board_id, "served_zones": dashboard.build_board_view(board_id)["served_zones"]}


@router.get("/electrical/zones/{zone_id}/electrical")
def zone_electrical(zone_id: str):
    _require(cfg.OUT_MAPPING / "zones.csv")
    v = dashboard.build_zone_view(zone_id)
    if not v.get("eplus_zone_name") and not v.get("assigned_boards"):
        raise HTTPException(404, f"zone '{zone_id}' not found")
    return v


@router.get("/electrical/floors/{floor_id}")
def floor(floor_id: str):
    _require(cfg.OUT_ELEC / "electrical_boards.csv")
    return dashboard.build_floor_view(floor_id)


@router.get("/electrical/load-points/{load_point_id}")
def load_point(load_point_id: str):
    _require(cfg.OUT_ELEC / "electrical_load_points.csv")
    for r in C.read_rows_csv(cfg.OUT_ELEC / "electrical_load_points.csv"):
        if r["load_point_id"] == load_point_id:
            circ = next((c for c in C.read_rows_csv(cfg.OUT_ELEC / "load_to_circuit_map.csv")
                         if c["load_point_id"] == load_point_id), {})
            return {**r, "circuit": circ}
    raise HTTPException(404, f"load point '{load_point_id}' not found")


@router.get("/graph/entities/{entity_id}/neighbors")
def neighbors(entity_id: str):
    _require(cfg.OUT_KG / "graph_edges.csv")
    return dashboard.build_graph_neighbors(entity_id)


@router.get("/graph/entities/{entity_id}/evidence")
def evidence(entity_id: str):
    _require(cfg.OUT_KG / "graph_edges.csv")
    edges = C.read_rows_csv(cfg.OUT_KG / "graph_edges.csv")
    out = [{"relationship": e["relationship_type"], "with": e["target_node_id"]
            if e["source_node_id"] == entity_id else e["source_node_id"],
            "method": e["method"], "confidence": e["confidence"], "evidence": e["evidence_json"]}
           for e in edges if entity_id in (e["source_node_id"], e["target_node_id"])]
    return {"entity_id": entity_id, "evidence": out[:200], "count": len(out)}


@router.get("/graph/rag/answer")
def rag_answer(question: str = Query(..., min_length=3)):
    from ...electrical.loaders import pgvector
    return pgvector.answer(question)

"""Load the electrical knowledge graph + board summaries into Postgres.

Idempotent (recreate-and-fill). Best-effort: raises if the database is
unreachable so the pipeline can report it as skipped.
"""
from __future__ import annotations

from sqlalchemy import text

from ...db import db_conn
from .. import canonical as C
from .. import config as cfg

DDL = """
CREATE TABLE IF NOT EXISTS el_graph_nodes (
  node_id TEXT PRIMARY KEY, node_type TEXT, name TEXT, floor_id TEXT, zone_id TEXT,
  ifc_global_id TEXT, eplus_name TEXT, value_class TEXT, confidence TEXT, properties_json JSONB);
CREATE TABLE IF NOT EXISTS el_graph_edges (
  edge_id TEXT PRIMARY KEY, source_node_id TEXT, target_node_id TEXT, relationship_type TEXT,
  weight DOUBLE PRECISION, method TEXT, confidence TEXT, evidence_json JSONB);
CREATE INDEX IF NOT EXISTS el_edges_src ON el_graph_edges(source_node_id);
CREATE INDEX IF NOT EXISTS el_edges_tgt ON el_graph_edges(target_node_id);
CREATE TABLE IF NOT EXISTS el_board_summary (
  board_id TEXT PRIMARY KEY, device_tag TEXT, floor_id TEXT, system_code TEXT,
  voltage_v DOUBLE PRECISION, phase_count DOUBLE PRECISION, rated_current_a DOUBLE PRECISION,
  total_kwh DOUBLE PRECISION, peak_total_kw DOUBLE PRECISION,
  estimated_peak_current_a DOUBLE PRECISION, loading_pct DOUBLE PRECISION, overload_status TEXT);
CREATE TABLE IF NOT EXISTS el_zone_board_allocation (
  zone_id TEXT, eplus_zone_name TEXT, load_category TEXT, board_id TEXT,
  weight DOUBLE PRECISION, mapping_confidence TEXT, mapping_method TEXT);
CREATE TABLE IF NOT EXISTS el_manual_review (
  item_id TEXT PRIMARY KEY, subject_id TEXT, subject_type TEXT, reason TEXT,
  recommended_action TEXT, confidence TEXT);
"""


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load() -> dict:
    nodes = C.read_rows_csv(cfg.OUT_KG / "graph_nodes.csv")
    edges = C.read_rows_csv(cfg.OUT_KG / "graph_edges.csv")
    boards = C.read_rows_csv(cfg.OUT_ELEC / "board_annual_summary.csv")
    alloc = C.read_rows_csv(cfg.OUT_ELEC / "zone_load_to_board_allocation.csv")
    reviews = C.read_rows_csv(cfg.OUT_ELEC / "manual_review_items.csv")

    with db_conn() as conn:
        for stmt in DDL.strip().split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
        for t in ("el_graph_nodes", "el_graph_edges", "el_board_summary",
                  "el_zone_board_allocation", "el_manual_review"):
            conn.execute(text(f"TRUNCATE {t}"))

        conn.execute(text("""INSERT INTO el_graph_nodes
            (node_id,node_type,name,floor_id,zone_id,ifc_global_id,eplus_name,value_class,confidence,properties_json)
            VALUES (:node_id,:node_type,:name,:floor_id,:zone_id,:ifc_global_id,:eplus_name,:value_class,:confidence,
                    CAST(:properties_json AS JSONB)) ON CONFLICT (node_id) DO NOTHING"""),
            [{k: n.get(k) for k in ("node_id", "node_type", "name", "floor_id", "zone_id",
              "ifc_global_id", "eplus_name", "value_class", "confidence", "properties_json")} for n in nodes])

        conn.execute(text("""INSERT INTO el_graph_edges
            (edge_id,source_node_id,target_node_id,relationship_type,weight,method,confidence,evidence_json)
            VALUES (:edge_id,:source_node_id,:target_node_id,:relationship_type,:weight,:method,:confidence,
                    CAST(:evidence_json AS JSONB)) ON CONFLICT (edge_id) DO NOTHING"""),
            [{"edge_id": e["edge_id"], "source_node_id": e["source_node_id"],
              "target_node_id": e["target_node_id"], "relationship_type": e["relationship_type"],
              "weight": _f(e.get("weight")), "method": e.get("method"), "confidence": e.get("confidence"),
              "evidence_json": e.get("evidence_json") or "{}"} for e in edges])

        conn.execute(text("""INSERT INTO el_board_summary
            (board_id,device_tag,floor_id,system_code,voltage_v,phase_count,rated_current_a,
             total_kwh,peak_total_kw,estimated_peak_current_a,loading_pct,overload_status)
            VALUES (:board_id,:device_tag,:floor_id,:system_code,:voltage_v,:phase_count,:rated_current_a,
                    :total_kwh,:peak_total_kw,:estimated_peak_current_a,:loading_pct,:overload_status)
            ON CONFLICT (board_id) DO NOTHING"""),
            [{"board_id": b["board_id"], "device_tag": b.get("device_tag"), "floor_id": b.get("floor_id"),
              "system_code": b.get("system_code"), "voltage_v": _f(b.get("voltage_v")),
              "phase_count": _f(b.get("phase_count")), "rated_current_a": _f(b.get("rated_current_a")),
              "total_kwh": _f(b.get("total_kwh")), "peak_total_kw": _f(b.get("peak_total_kw")),
              "estimated_peak_current_a": _f(b.get("estimated_peak_current_a")),
              "loading_pct": _f(b.get("loading_pct")), "overload_status": b.get("overload_status")}
             for b in boards])

        conn.execute(text("""INSERT INTO el_zone_board_allocation
            (zone_id,eplus_zone_name,load_category,board_id,weight,mapping_confidence,mapping_method)
            VALUES (:zone_id,:eplus_zone_name,:load_category,:board_id,:weight,:mapping_confidence,:mapping_method)"""),
            [{"zone_id": a["zone_id"], "eplus_zone_name": a.get("eplus_zone_name"),
              "load_category": a["load_category"], "board_id": a["board_id"], "weight": _f(a.get("weight")),
              "mapping_confidence": a.get("mapping_confidence"), "mapping_method": a.get("mapping_method")}
             for a in alloc])

        if reviews:
            conn.execute(text("""INSERT INTO el_manual_review
                (item_id,subject_id,subject_type,reason,recommended_action,confidence)
                VALUES (:item_id,:subject_id,:subject_type,:reason,:recommended_action,:confidence)
                ON CONFLICT (item_id) DO NOTHING"""),
                [{k: r.get(k) for k in ("item_id", "subject_id", "subject_type", "reason",
                  "recommended_action", "confidence")} for r in reviews])

    return {"nodes": len(nodes), "edges": len(edges), "boards": len(boards),
            "allocations": len(alloc), "manual_review": len(reviews)}


if __name__ == "__main__":
    print(load())

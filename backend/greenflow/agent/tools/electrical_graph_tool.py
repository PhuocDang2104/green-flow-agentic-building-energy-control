"""Agent tool over the electrical knowledge graph (file-backed artifacts).

Lets the LangGraph agent reason about boards, supply, demand and provenance
without a database, reusing the dashboard view builders and the RAG retriever.
Every result carries provenance/confidence so the agent can answer per the
graph-RAG answer policy (measured / simulated / IFC-derived / inferred / assumed).
"""
from __future__ import annotations

from ...electrical import canonical as C
from ...electrical import config as cfg
from ...electrical import dashboard


def available() -> bool:
    return (cfg.OUT_ELEC / "board_annual_summary.csv").exists()


def neighbors(entity_id: str) -> dict:
    return dashboard.build_graph_neighbors(entity_id)


def board_demand(board_id: str) -> dict:
    return dashboard.build_board_view(board_id)


def served_zones(board_id: str) -> list[dict]:
    return dashboard.build_board_view(board_id).get("served_zones", {})


def zone_supply(zone_id: str) -> dict:
    """Which board(s) likely supply a zone, with confidence + provenance."""
    return dashboard.build_zone_view(zone_id)


def top_boards(n: int = 10) -> list[dict]:
    rows = C.read_rows_csv(cfg.OUT_ELEC / "board_annual_summary.csv")
    def _f(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    rows = [r for r in rows if r["board_id"] != cfg.UNMAPPED_BOARD_ID]
    rows.sort(key=lambda r: -_f(r.get("peak_total_kw")))
    return [{"board_id": r["board_id"], "device_tag": r.get("device_tag"),
             "floor_id": r.get("floor_id"), "peak_total_kw": _f(r.get("peak_total_kw")),
             "total_kwh": _f(r.get("total_kwh")), "overload_status": r.get("overload_status"),
             "value_class": "spatially_inferred"} for r in rows[:n]]


def boards_missing_rating() -> list[dict]:
    rows = C.read_rows_csv(cfg.OUT_ELEC / "board_annual_summary.csv")
    return [{"board_id": r["board_id"], "device_tag": r.get("device_tag")}
            for r in rows if r.get("overload_status") == "rating_missing"]


def answer(question: str) -> dict:
    from ...electrical.loaders import pgvector
    return pgvector.answer(question)

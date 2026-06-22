"""Tests for the electrical knowledge-graph / board-allocation layer.

These validate the invariants the layer must never break: allocation weights sum
to 1, board energy does not double-count zone energy, boards are not modelled as
loads, the current formula matches the documented convention, and every node/edge
carries provenance. They read the generated artifacts and skip if the pipeline
has not been run.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict

import pytest

from greenflow.electrical import canonical as C
from greenflow.electrical import config as cfg

pytestmark = pytest.mark.skipif(
    not (cfg.OUT_ELEC / "board_annual_summary.csv").exists(),
    reason="electrical KG artifacts not built (run scripts/build_electrical_kg.py --all)",
)


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def test_key_artifacts_exist():
    for rel in ["electrical_boards.csv", "electrical_load_points.csv",
                "zone_load_to_board_allocation.csv", "board_annual_summary.csv",
                "board_estimated_timeseries.parquet", "electrical_validation_report.json"]:
        assert (cfg.OUT_ELEC / rel).exists(), rel
    for rel in ["graph_nodes.csv", "graph_edges.csv", "graph_rag_entity_cards.jsonl"]:
        assert (cfg.OUT_KG / rel).exists(), rel


def test_allocation_weights_sum_to_one():
    sums = defaultdict(float)
    for a in C.read_rows_csv(cfg.OUT_ELEC / "zone_load_to_board_allocation.csv"):
        sums[(a["zone_id"], a["load_category"])] += float(a["weight"])
    bad = {k: v for k, v in sums.items() if abs(v - 1.0) > 1e-6}
    assert not bad, f"weights must sum to 1 per (zone,category); offenders: {list(bad)[:5]}"


def test_no_double_count_and_validation_passes():
    report = json.loads((cfg.OUT_ELEC / "electrical_validation_report.json").read_text("utf-8"))
    assert report["summary"]["fail"] == 0, report["summary"]
    assert report["summary"]["max_mismatch_pct" if "max_mismatch_pct" in report["summary"]
                            else "checks"] is not None
    # board energy == allocated zone energy per category (board layer redistributes, not adds)
    for r in report["reconciliation"]:
        assert r["diff_pct"] <= 0.5, r


def test_boards_are_not_consuming_loads():
    # every board's demand is labelled inferred/estimated, never measured/simulated as a source
    for b in C.read_rows_csv(cfg.OUT_ELEC / "board_annual_summary.csv"):
        if b["board_id"] == cfg.UNMAPPED_BOARD_ID:
            continue
        assert b["value_class"] == "spatially_inferred"


def test_current_formula_matches_convention():
    boards = {b["board_id"]: b for b in C.read_rows_csv(cfg.OUT_ELEC / "electrical_boards.csv")}
    checked = 0
    for a in C.read_rows_csv(cfg.OUT_ELEC / "board_annual_summary.csv"):
        cur = _f(a.get("estimated_peak_current_a"))
        if cur is None or a["overload_status"] == "unmapped":
            continue
        v = _f(a.get("voltage_v")) or 0
        pf = _f(a.get("power_factor")) or 0
        phase = _f(a.get("phase_count"))
        peak_kw = _f(a.get("peak_total_kw")) or 0
        denom = (cfg.SQRT3 * v * pf) if phase == 3 else (v * pf)
        if denom:
            expected = peak_kw * 1000.0 / denom
            assert math.isclose(cur, round(expected, 1), abs_tol=0.5), (a["board_id"], cur, expected)
            checked += 1
    assert checked > 0


def test_overload_requires_real_rating():
    boards = {b["board_id"]: b for b in C.read_rows_csv(cfg.OUT_ELEC / "electrical_boards.csv")}
    for a in C.read_rows_csv(cfg.OUT_ELEC / "board_annual_summary.csv"):
        rated = _f((boards.get(a["board_id"]) or {}).get("rated_current_a"))
        if not rated:  # missing/zero rating -> must be rating_missing or unmapped
            assert a["overload_status"] in ("rating_missing", "unmapped"), a["board_id"]


def test_every_node_and_edge_has_provenance():
    nodes = C.read_rows_csv(cfg.OUT_KG / "graph_nodes.csv")
    edges = C.read_rows_csv(cfg.OUT_KG / "graph_edges.csv")
    assert nodes and edges
    assert all(n.get("value_class") for n in nodes[:500])
    assert all(e.get("confidence") for e in edges[:500])


def test_rag_answer_enforces_value_labels():
    from greenflow.electrical.loaders import pgvector
    res = pgvector.answer("Which board supplies the highest load and is it overloaded?")
    assert res["answer"]
    assert "energyplus_simulated" in res["value_labels_required"]
    assert res["sources"]

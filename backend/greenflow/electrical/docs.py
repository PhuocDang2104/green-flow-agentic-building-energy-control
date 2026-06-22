"""Phase 12 — documentation. Generates the README + schema + data dictionary +
assumptions/limitations + graph-RAG and dashboard guides, stating plainly what
is simulated vs estimated and that boards are not consuming loads."""
from __future__ import annotations

from . import canonical as C
from . import config as cfg


def _columns(path) -> list[str]:
    rows = C.read_rows_csv(path)
    return list(rows[0].keys()) if rows else []


def run() -> dict[str, int]:
    cfg.ensure_dirs()
    C.write_text(cfg.OUT_ELEC / "README_ELECTRICAL_DISTRIBUTION_DIGITAL_TWIN.md", _README)
    C.write_text(cfg.OUT_ELEC / "ELECTRICAL_GRAPH_SCHEMA.md", _GRAPH_SCHEMA)
    C.write_text(cfg.OUT_ELEC / "ELECTRICAL_ASSUMPTIONS_AND_LIMITATIONS.md", _ASSUMPTIONS)
    C.write_text(cfg.OUT_ELEC / "GRAPH_RAG_USAGE_GUIDE.md", _RAG_GUIDE)
    C.write_text(cfg.OUT_ELEC / "DASHBOARD_ELECTRICAL_VIEW_GUIDE.md", _DASH_GUIDE)

    described = {
        "electrical_boards.csv": "Distribution boards (IFC-derived assets, never loads).",
        "electrical_load_points.csv": "Light fixtures, outlets, alarms with design power / system code.",
        "electrical_cable_assets.csv": "Cable-tray segments + fittings.",
        "electrical_circuits.csv": "Circuits (one per board×category; system-grouped or pseudo).",
        "zone_load_to_board_allocation.csv": "Per (zone,category) board weights (sum to 1).",
        "board_annual_summary.csv": "Per-board estimated energy/peak/current/overload.",
        "board_peak_demand_summary.csv": "Per-board peak demand + timestamp.",
        "phase_balance_summary.csv": "Phase imbalance (not available — no per-phase allocation).",
        "energy_reconciliation_by_board_category.csv": "Zone vs board vs meter energy by category.",
        "manual_review_items.csv": "Items needing human confirmation before control use.",
    }
    dd = []
    for fname, desc in described.items():
        for col in _columns(cfg.OUT_ELEC / fname):
            dd.append({"file": fname, "column": col, "file_description": desc})
    C.write_rows_csv(cfg.OUT_ELEC / "ELECTRICAL_DATA_DICTIONARY.csv", dd)
    return {"docs": 6, "data_dictionary_rows": len(dd)}


_README = """# GreenFlow — Electrical Distribution Digital-Twin Layer

A **separate graph + allocation layer** on top of the existing zone-level EnergyPlus
dataset. It adds electrical-distribution reasoning (boards, circuits, load points,
cable trays), an estimated board-demand timeseries, a building knowledge graph,
graph-RAG cards, and a 3D dashboard manifest — **without** re-simulating or editing
the IDF, and **without** double-counting boards as energy.

## Pipeline (each phase rerunnable)
`python scripts/build_electrical_kg.py --all`  (or `--phase ele|spatial|energy|alloc|hvac|graph|timeseries|rag|dashboard|validate|docs`)

1. audit → `knowledge_graph_build/audit/`
2. ele → `electrical_distribution/electrical_{boards,load_points,cable_assets,asset_property_audit}.csv`
3. spatial → `knowledge_graph_build/mapping/`
4. energy → `knowledge_graph_build/energy/`
5. alloc → `electrical_distribution/{zone_load_to_board_allocation,electrical_circuits,*_map}.csv`
6. hvac → `knowledge_graph_build/hvac_*`
7. graph → `knowledge_graph_build/graph_*` (+ `electrical_graph_*`)
8. timeseries → `electrical_distribution/board_*` (parquet + summaries)
9. rag → `knowledge_graph_build/graph_rag_*`
10. dashboard → `electrical_distribution/dashboard_electrical_manifest.json`
11. validate → `electrical_distribution/electrical_validation_report.json`
12. docs → this folder

## Key facts
- The IDF remains a **zone-level EnergyPlus** model; board/circuit/phase analytics are an
  estimated allocation layer.
- **Electrical boards are not consuming loads.** Board demand = simulated zone energy
  redistributed by inferred allocation (validated to conserve energy, ~0% mismatch).
- Board demand is **estimated** unless real panel-meter data exists.
- Circuit/phase results are **exact only** with explicit circuit evidence; lighting/plug
  use IFC Finnish system codes (naming evidence), HVAC uses pseudo circuits.
- Every value/edge is labelled measured / EnergyPlus-simulated / IFC-derived / inferred /
  assumed / manual-review.
- This is useful for engineering reasoning + dashboards, **not** a certified electrical
  protection study unless verified against real design schedules and measurements.
"""

_GRAPH_SCHEMA = """# Electrical Graph Schema

See `knowledge_graph_build/graph_schema.md` for live node/edge type counts.

Node types: Building, Floor, ThermalZone, EnergyPlusZone, ElectricalBoard, Circuit,
LightFixture, Outlet, Alarm, CableTray, HVACDevice, PTAC, Meter, WeatherTimeseries.

Edge types: BUILDING_HAS_FLOOR, FLOOR_HAS_ROOM, ZONE_MAPS_TO_EPLUS_ZONE,
OBJECT_LOCATED_ON_FLOOR, OBJECT_ASSIGNED_TO_ZONE, BOARD_SUPPLIES_CIRCUIT,
CIRCUIT_SUPPLIES_LOAD_POINT, ZONE_LOAD_ALLOCATED_TO_BOARD, ZONE_LOAD_ALLOCATED_TO_CIRCUIT,
HVAC_DEVICE_SERVES_ZONE, ENERGYPLUS_PTAC_REPRESENTS_HVAC_FOR, ZONE_HAS_HVAC_LOAD,
WEATHER_CONTEXT_FOR_HVAC_LOAD, METER_MEASURES_ENTITY.

Every node carries `source_system`, `value_class`, `confidence`; every edge carries
`source`, `method`, `confidence`, `evidence_json`.
"""

_ASSUMPTIONS = """# Electrical Assumptions & Limitations

- **Energy source:** patched `final_zone_device_power_timeseries` (EnergyPlus simulated),
  scenario `openmeteo_2025_30min_baseline`, 30-min, full-year. EnergyPlus is not re-run.
- **Board ratings:** the IFC `Nimellisvirta` (rated current) is largely a placeholder `0`
  → most boards are `rating_missing`; overload is **not** asserted for them (demand ranking only).
- **Power factor / voltage:** when absent from IFC, current uses assumed defaults
  (PF=%(pf)s, 230/400 V) and is flagged `assumed_default`.
- **No IfcOutlet→circuit schedule:** plug loads use IFC outlet system codes + proximity;
  where absent, a **pseudo plug circuit** (low confidence).
- **HVAC:** no IFC HVAC→board link; HVAC load is a **pseudo HVAC circuit** on the floor
  main board (low). The EnergyPlus PTAC is a *representative model* of zone HVAC, not a
  1:1 map to IFC HVAC devices.
- **Spatial:** floor assignment is by IFC storey containment (high); zone-per-object is by
  nearest space centroid (medium/low) and is not required for allocation.
- **Phase balance:** not computed (no per-phase load allocation).
- Not a certified protection/coordination study.
""" % {"pf": cfg.DEFAULT_POWER_FACTOR}

_RAG_GUIDE = """# Graph-RAG Usage Guide

Cards: `knowledge_graph_build/graph_rag_entity_cards.jsonl` (+ relationship cards) are
embedded into the pgvector `electrical_kg` collection by `loaders/pgvector.py`.

Ask via `GET /api/graph/rag/answer?question=...`. The endpoint retrieves the most
relevant cards, then answers under `graph_rag_answer_policy.md`: every value is labelled
(measured / simulated / IFC-derived / inferred / assumed / manual-review) and topology is
never overclaimed. See `graph_rag_example_questions.md` and `graph_rag_retrieval_queries.sql`.
"""

_DASH_GUIDE = """# Dashboard Electrical View Guide

`dashboard_electrical_manifest.json` drives the frontend: layers (boards, load points,
cable trays, zones, HVAC), metrics (peak kW, annual kWh, loading %), colour scales
(loading/overload), entity types, click→API actions, and badges (warning, low-confidence,
manual-review, rating-missing).

Views: building overview, floor electrical, zone energy, board, circuit, graph-RAG.
Board/zone/floor payloads come from `backend/greenflow/electrical/dashboard.py` `build_*`
functions, served by `api/routers/electrical.py`.
"""


if __name__ == "__main__":
    print(run())

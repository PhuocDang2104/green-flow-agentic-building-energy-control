# GreenFlow — Electrical Distribution Digital-Twin Layer

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

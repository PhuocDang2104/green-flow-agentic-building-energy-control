"""Phase 9 — graph-RAG artifacts.

Builds retrieval-ready entity/relationship cards (one text blob + structured
provenance per card, for embedding into pgvector) plus the schema, retrieval
queries, example questions, and the answer policy that forces every value to be
labelled measured / simulated / IFC-derived / inferred / assumed / manual-review.
"""
from __future__ import annotations

from collections import defaultdict

from . import canonical as C
from . import config as cfg
from ..zone_naming import zone_display_name_from_mapping

ENTITY_CARDS = cfg.OUT_KG / "graph_rag_entity_cards.jsonl"
REL_CARDS = cfg.OUT_KG / "graph_rag_relationship_cards.jsonl"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def run() -> dict[str, int]:
    cfg.ensure_dirs()
    boards = {b["board_id"]: b for b in C.read_rows_csv(cfg.OUT_ELEC / "electrical_boards.csv")}
    ann = {a["board_id"]: a for a in C.read_rows_csv(cfg.OUT_ELEC / "board_annual_summary.csv")}
    zones = {z["zone_id"]: z for z in C.read_rows_csv(cfg.OUT_MAPPING / "zones.csv")}
    alloc = C.read_rows_csv(cfg.OUT_ELEC / "zone_load_to_board_allocation.csv")

    board_zones: dict[str, set] = defaultdict(set)
    zone_boards: dict[str, list] = defaultdict(list)
    for a in alloc:
        board_zones[a["board_id"]].add(a["zone_id"])
        zone_boards[a["zone_id"]].append((a["board_id"], a["load_category"], a["weight"], a["mapping_confidence"]))

    cards: list[dict] = []

    # ---- board cards ----
    for bid, b in boards.items():
        a = ann.get(bid, {})
        served = sorted(board_zones.get(bid, []))
        status = a.get("overload_status", "rating_missing")
        rated = _f(b.get("rated_current_a"))
        caveats = []
        if status == "rating_missing":
            caveats.append("rated current missing/zero → overload cannot be assessed (demand ranking only)")
        if a.get("pf_source") == "assumed_default" or a.get("voltage_source") == "assumed_default":
            caveats.append("estimated current uses assumed power-factor/voltage")
        caveats.append("board demand is EnergyPlus-simulated zone energy × inferred allocation (estimated)")
        text = (f"Electrical distribution board {b.get('device_tag') or bid} on floor "
                f"{b.get('floor_id')}, system {b.get('system_code')} ({b.get('system_name')}). "
                f"{b.get('voltage_v')} V, {b.get('phase_count')}-phase. "
                f"Estimated annual energy {a.get('total_kwh')} kWh, peak {a.get('peak_total_kw')} kW, "
                f"estimated peak current {a.get('estimated_peak_current_a')} A, status {status}. "
                f"Serves ~{len(served)} zones. Rated current "
                f"{'not set' if not rated else rated}.")
        cards.append({"card_id": bid, "card_type": "entity", "entity_type": "ElectricalBoard",
                      "title": f"Board {b.get('device_tag') or bid}", "text": text,
                      "properties": {k: b.get(k) for k in ("device_tag", "voltage_v", "phase_count",
                                     "rated_current_a", "system_code", "system_name", "floor_id")},
                      "demand": {k: a.get(k) for k in ("total_kwh", "peak_total_kw",
                                 "estimated_peak_current_a", "loading_pct", "overload_status")},
                      "provenance": "IFC-derived asset; demand estimated from EnergyPlus-simulated zone "
                                    "energy via inferred allocation",
                      "confidence": "ifc_derived asset; medium/low allocation", "caveats": caveats,
                      "linked_entities": served[:25], "recommended_dashboard_view": "board_view"})

    # ---- zone cards ----
    for zid, z in zones.items():
        zb = zone_boards.get(zid, [])
        bset = sorted({x[0] for x in zb})
        confs = sorted({x[3] for x in zb})
        zone_name = zone_display_name_from_mapping(z)
        text = (f"Thermal zone {zone_name} ({z.get('room_type')}) on floor {z.get('storey') or z.get('floor_id')}, "
                f"area {z.get('area_m2')} m². EnergyPlus zone {z.get('eplus_zone_name')}. "
                f"Lights/equipment/HVAC electricity is EnergyPlus-simulated. Estimated to be supplied by "
                f"boards {', '.join(b for b in bset if b != cfg.UNMAPPED_BOARD_ID) or 'unmapped'} "
                f"(allocation confidence: {', '.join(confs)}).")
        cards.append({"card_id": zid, "card_type": "entity", "entity_type": "ThermalZone",
                      "title": f"Zone {zone_name}", "text": text,
                      "properties": {k: z.get(k) for k in ("eplus_zone_name", "room_type", "area_m2",
                                     "floor_id", "usage_type")},
                      "provenance": "IFC space + EnergyPlus simulated energy",
                      "confidence": "high (identity)", "caveats": ["supplying board(s) are inferred"],
                      "linked_entities": bset, "recommended_dashboard_view": "zone_energy_view"})

    # ---- floor + building + meter cards ----
    for fl in C.read_rows_csv(cfg.OUT_MAPPING / "floors.csv"):
        nb = sum(1 for b in boards.values() if b.get("floor_id") == fl["floor_id"])
        cards.append({"card_id": fl["floor_id"], "card_type": "entity", "entity_type": "Floor",
                      "title": f"Floor {fl['name']}",
                      "text": f"Building floor {fl['name']} (index {fl['floor_index']}, elevation "
                              f"{fl['elevation_m']} m) with {nb} electrical boards.",
                      "properties": fl, "provenance": "IFC-derived", "confidence": "exact",
                      "caveats": [], "linked_entities": [], "recommended_dashboard_view": "floor_electrical_view"})

    C.write_jsonl(ENTITY_CARDS, cards)

    # ---- relationship cards (one per relationship type) ----
    rels = [
        ("ZONE_LOAD_ALLOCATED_TO_BOARD", "A zone's simulated load (by category) is estimated to be supplied "
         "by this board with a weight; method/confidence on the edge.", "spatially/naming inferred"),
        ("BOARD_SUPPLIES_CIRCUIT", "A board supplies a (pseudo or system-grouped) circuit.", "derived"),
        ("CIRCUIT_SUPPLIES_LOAD_POINT", "A circuit supplies a light fixture/outlet, grouped by Finnish "
         "system code + floor proximity.", "naming/medium"),
        ("OBJECT_LOCATED_ON_FLOOR", "An electrical object is on a floor via IFC storey containment.", "high"),
        ("OBJECT_ASSIGNED_TO_ZONE", "An object is assigned to the nearest IfcSpace on its floor.", "medium/low"),
        ("ZONE_MAPS_TO_EPLUS_ZONE", "Identity between the IFC space zone and the EnergyPlus zone.", "exact"),
        ("ENERGYPLUS_PTAC_REPRESENTS_HVAC_FOR", "The EnergyPlus PTAC is the representative model of a zone's "
         "HVAC; not a 1:1 map to IFC HVAC devices.", "representative_model"),
        ("HVAC_DEVICE_SERVES_ZONE", "An IFC HVAC terminal serves the nearest zone on its floor.", "medium/low"),
        ("METER_MEASURES_ENTITY", "A building electricity meter measures the building.", "exact"),
    ]
    rel_cards = [{"card_id": r, "card_type": "relationship", "relationship_type": r, "title": r,
                  "text": f"{r}: {desc}", "provenance": prov,
                  "recommended_dashboard_view": "graph_rag_view"} for (r, desc, prov) in rels]
    C.write_jsonl(REL_CARDS, rel_cards)

    _docs()
    return {"entity_cards": len(cards), "relationship_cards": len(rel_cards)}


def _docs() -> None:
    C.write_text(cfg.OUT_KG / "graph_rag_answer_policy.md", _ANSWER_POLICY)
    C.write_text(cfg.OUT_KG / "graph_rag_example_questions.md", _EXAMPLE_Q)
    C.write_text(cfg.OUT_KG / "graph_rag_schema.md", _SCHEMA)
    C.write_text(cfg.OUT_KG / "graph_rag_retrieval_queries.sql", _QUERIES)


_ANSWER_POLICY = """# Graph-RAG Answer Policy

When answering electrical / energy questions over this graph, the agent MUST:

1. **Label every value** with how it was obtained:
   - `measured` — from a real meter/sensor (only the building meters + weather here)
   - `energyplus_simulated` — zone Lights/Equipment/HVAC electricity from the gold dataset
   - `ifc_derived` — board/fixture/cable attributes read from the IFC (voltage, phase, system code)
   - `spatially_inferred` — assignment by floor containment / nearest space
   - `naming_inferred` — grouping by Finnish system code (`Järjestelmien tunnukset`)
   - `assumption_based` — estimated current using assumed power-factor/voltage
   - `manual_review` — insufficient evidence; do not use for automated control/risk
2. **Never overclaim topology.** Board→zone supply is *estimated allocation*, not a verified
   circuit schedule, unless an edge confidence is `exact`.
3. **Overload:** only state overload/loading-% when a board has a real `rated_current_a`.
   Otherwise say `rating_missing` and give demand ranking only.
4. **Boards are distribution assets**, never additional consumption; board demand is the
   redistribution of simulated zone energy.
5. Always surface the **confidence** and any **manual-review** flags, and cite the
   evidence (edge method, distance, system code).
"""

_EXAMPLE_Q = """# Graph-RAG Example Questions

| question | answered from |
|---|---|
| Which board likely supplies this zone? | `ZONE_LOAD_ALLOCATED_TO_BOARD` edges + zone card |
| Which zones contribute most to a board's peak demand? | board timeseries + allocation weights |
| Which board has the highest estimated load? | `board_annual_summary.csv` (peak_total_kw) |
| Which load categories dominate this board? | `board_load_category_timeseries.parquet` |
| Which zones have high HVAC electricity during hot weather? | gold zone table × `final_weather_timeseries` |
| Which boards have missing ratings? | `board_annual_summary` overload_status=rating_missing |
| Which mappings are low confidence? | edges with confidence low/manual_review |
| Which electrical objects are unmapped? | `manual_review_items.csv` |
| Which HVAC devices serve a high-energy zone? | `HVAC_DEVICE_SERVES_ZONE` edges |
| Which IFC evidence supports this board→zone mapping? | edge `evidence_json` + system code |
| Is this overload warning measured, simulated, or estimated? | answer policy → estimated/rating_missing |
| What must be reviewed before using this for control? | `manual_review_items.csv` |
"""

_SCHEMA = """# Graph-RAG Schema

Cards (JSONL) are embedded into the `electrical_kg` pgvector collection:

- **entity cards** (`graph_rag_entity_cards.jsonl`): boards, zones, floors — each with
  `text` (embedded), `properties`, `demand`, `provenance`, `confidence`, `caveats`,
  `linked_entities`, `recommended_dashboard_view`.
- **relationship cards** (`graph_rag_relationship_cards.jsonl`): one per relationship type
  describing meaning + provenance.

Backing structured data: `graph_nodes.csv` / `graph_edges.csv` (full graph),
`board_annual_summary.csv`, `board_estimated_timeseries.parquet`,
`zone_load_to_board_allocation.csv`, `manual_review_items.csv`.
"""

_QUERIES = """-- Graph-RAG retrieval queries (DuckDB over the generated artifacts)

-- 1. Which board supplies a given zone (and how confident)?
SELECT target_node_id AS board_id, notes AS category, weight, confidence, evidence_json
FROM read_csv_auto('graph_edges.csv')
WHERE relationship_type='ZONE_LOAD_ALLOCATED_TO_BOARD' AND source_node_id = ?;

-- 2. Highest estimated board demand.
SELECT board_id, device_tag, total_kwh, peak_total_kw, overload_status
FROM read_csv_auto('board_annual_summary.csv') ORDER BY peak_total_kw DESC LIMIT 10;

-- 3. Top contributing zones to a board (annual energy).
SELECT source_node_id AS zone_id, notes AS category, weight
FROM read_csv_auto('graph_edges.csv')
WHERE relationship_type='ZONE_LOAD_ALLOCATED_TO_BOARD' AND target_node_id = ?
ORDER BY weight DESC;

-- 4. Boards with missing ratings.
SELECT board_id, device_tag, floor_id FROM read_csv_auto('board_annual_summary.csv')
WHERE overload_status='rating_missing';

-- 5. Low-confidence / manual-review mappings.
SELECT * FROM read_csv_auto('graph_edges.csv') WHERE confidence IN ('low','manual_review');

-- 6. Neighbours of an entity (graph view).
SELECT * FROM read_csv_auto('graph_edges.csv')
WHERE source_node_id = ? OR target_node_id = ?;
"""


if __name__ == "__main__":
    print(run())

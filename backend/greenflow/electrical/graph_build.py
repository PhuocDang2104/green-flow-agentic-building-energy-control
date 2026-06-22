"""Phase 5 — assemble the unified building knowledge graph.

Reads the Phase 2/3/4/6 artifacts and emits nodes + edges spanning the spatial,
energy, electrical, and provenance subgraphs (CSV + JSONL), a schema, and a data
dictionary. A focused electrical-subgraph mirror is written under
data/electrical_distribution as well.
"""
from __future__ import annotations

from . import canonical as C
from . import config as cfg
from . import gold
from .provenance import Confidence, SourceSystem, ValueClass

NODE_FIELDS = ["node_id", "node_type", "name", "label", "source_system", "source_file",
               "ifc_global_id", "eplus_name", "xeokit_object_id", "zone_id", "floor_id",
               "room_id", "coordinates", "properties_json", "value_class", "confidence", "notes"]
EDGE_FIELDS = ["edge_id", "source_node_id", "target_node_id", "relationship_type", "direction",
               "weight", "source", "method", "confidence", "evidence_json", "notes"]


def run() -> dict[str, int]:
    cfg.ensure_dirs()
    nodes: dict[str, C.Entity] = {}
    edges: list[C.Edge] = []

    def add(e: C.Entity):
        nodes.setdefault(e.entity_id, e)

    def edge(s, t, rel, **kw):
        edges.append(C.Edge(s, t, rel, **kw))

    # ---- spatial: building / floors / zones / eplus zones ----
    add(C.Entity(C.entity_id("building", cfg.BUILDING_KEY), "Building", cfg.BUILDING_NAME,
                 source_system=SourceSystem.IFC_ARCH, source_file="ARCH_AsBuilt_enriched.ifc",
                 value_class=ValueClass.IFC_DERIVED, confidence=Confidence.EXACT))
    bnode = C.entity_id("building", cfg.BUILDING_KEY)

    for fl in C.read_rows_csv(cfg.OUT_MAPPING / "floors.csv"):
        add(C.Entity(fl["floor_id"], "Floor", fl["name"], source_system=SourceSystem.IFC_ARCH,
                     source_file="ARCH_AsBuilt_enriched.ifc", floor_id=fl["floor_id"],
                     value_class=ValueClass.IFC_DERIVED, confidence=Confidence.EXACT,
                     properties={"floor_index": fl["floor_index"], "elevation_m": fl["elevation_m"]}))
        edge(bnode, fl["floor_id"], "BUILDING_HAS_FLOOR", source=SourceSystem.IFC_ARCH,
             method="ifc_aggregation", confidence=Confidence.EXACT)

    for z in C.read_rows_csv(cfg.OUT_MAPPING / "zones.csv"):
        zid, ez = z["zone_id"], z.get("eplus_zone_name", "")
        add(C.Entity(zid, "ThermalZone", z.get("long_name") or zid, ifc_global_id=z["ifc_global_id"],
                     eplus_name=ez, floor_id=z["floor_id"], room_id=z["room_id"], zone_id=zid,
                     source_system=SourceSystem.IFC_ARCH, source_file="ARCH_AsBuilt_enriched.ifc",
                     value_class=ValueClass.IFC_DERIVED, confidence=Confidence.HIGH,
                     properties={"room_type": z.get("room_type"), "area_m2": z.get("area_m2"),
                                 "volume_m3": z.get("volume_m3"), "usage_type": z.get("usage_type")}))
        if z["floor_id"]:
            edge(z["floor_id"], zid, "FLOOR_HAS_ROOM", source=SourceSystem.IFC_ARCH,
                 method="ifc_storey_containment", confidence=Confidence.HIGH)
        if ez:
            ezid = C.eplus_zone_node_id(ez)
            add(C.Entity(ezid, "EnergyPlusZone", ez, eplus_name=ez, zone_id=zid, floor_id=z["floor_id"],
                         source_system=SourceSystem.ENERGYPLUS, source_file=cfg.IDF_FILE.name,
                         value_class=ValueClass.ENERGYPLUS_SIMULATED, confidence=Confidence.EXACT))
            edge(zid, ezid, "ZONE_MAPS_TO_EPLUS_ZONE", source=SourceSystem.GREENFLOW_POST,
                 method="gold_zone_id_identity", confidence=Confidence.EXACT)

    # ---- electrical assets ----
    for b in C.read_rows_csv(cfg.OUT_ELEC / "electrical_boards.csv"):
        add(C.Entity(b["board_id"], "ElectricalBoard", b.get("name") or b.get("device_tag") or b["board_id"],
                     label=b.get("device_tag"), ifc_global_id=b["ifc_global_id"], floor_id=b["floor_id"],
                     x=_f(b.get("x")), y=_f(b.get("y")), z=_f(b.get("z")),
                     source_system=SourceSystem.IFC_ELE, source_file="ELE_enriched.ifc",
                     value_class=ValueClass.IFC_DERIVED, confidence=Confidence.HIGH,
                     properties={k: b.get(k) for k in ("device_tag", "voltage_v", "phase_count",
                                 "rated_current_a", "power_factor", "system_code", "system_name",
                                 "board_kind")}))
    for lp in C.read_rows_csv(cfg.OUT_ELEC / "electrical_load_points.csv"):
        ntype = {"lighting": "LightFixture", "plug": "Outlet", "alarm": "Alarm"}.get(lp["load_kind"], "LoadPoint")
        add(C.Entity(lp["load_point_id"], ntype, lp.get("name") or lp["load_point_id"],
                     label=lp.get("device_tag"), ifc_global_id=lp["ifc_global_id"], floor_id=lp["floor_id"],
                     x=_f(lp.get("x")), y=_f(lp.get("y")), z=_f(lp.get("z")),
                     source_system=SourceSystem.IFC_ELE, source_file="ELE_enriched.ifc",
                     value_class=ValueClass.IFC_DERIVED, confidence=Confidence.HIGH,
                     properties={k: lp.get(k) for k in ("device_tag", "load_kind", "category",
                                 "voltage_v", "design_power_w", "power_factor", "system_code")}))
    for cb in C.read_rows_csv(cfg.OUT_ELEC / "electrical_cable_assets.csv"):
        add(C.Entity(cb["cable_id"], "CableTray", cb.get("name") or cb["cable_id"],
                     ifc_global_id=cb["ifc_global_id"], floor_id=cb["floor_id"],
                     x=_f(cb.get("x")), y=_f(cb.get("y")), z=_f(cb.get("z")),
                     source_system=SourceSystem.IFC_ELE, source_file="ELE_enriched.ifc",
                     value_class=ValueClass.IFC_DERIVED, confidence=Confidence.HIGH,
                     properties={k: cb.get(k) for k in ("size_label", "system_code", "system_name")}))

    for c in C.read_rows_csv(cfg.OUT_ELEC / "electrical_circuits.csv"):
        add(C.Entity(c["circuit_id"], "Circuit", c["circuit_id"], source_system=SourceSystem.DERIVED,
                     source_file="board_alloc", value_class=c.get("value_class") or ValueClass.NAMING_INFERRED,
                     confidence=c.get("confidence") or Confidence.LOW,
                     properties={k: c.get(k) for k in ("board_id", "category", "kind", "system_codes")}))
        edge(c["board_id"], c["circuit_id"], "BOARD_SUPPLIES_CIRCUIT", source=SourceSystem.DERIVED,
             method="board_alloc_circuit", confidence=c.get("confidence") or Confidence.LOW)

    # ---- locate objects on floor / zone ----
    for r in C.read_rows_csv(cfg.OUT_MAPPING / "object_to_floor_room_zone_map.csv"):
        oid = r["object_id"]
        if oid not in nodes:
            continue
        if r["floor_id"]:
            edge(oid, r["floor_id"], "OBJECT_LOCATED_ON_FLOOR", source=SourceSystem.IFC_ELE,
                 method=r["mapping_method"], confidence=r["floor_confidence"])
        if r["zone_id"]:
            edge(oid, r["zone_id"], "OBJECT_ASSIGNED_TO_ZONE", source=SourceSystem.IFC_ELE,
                 method=r["mapping_method"], confidence=r["zone_confidence"],
                 evidence={"distance_m": r.get("distance_m")})

    # ---- circuit -> load point ----
    for r in C.read_rows_csv(cfg.OUT_ELEC / "load_to_circuit_map.csv"):
        edge(r["circuit_id"], r["load_point_id"], "CIRCUIT_SUPPLIES_LOAD_POINT", source=SourceSystem.DERIVED,
             method=r["mapping_method"], confidence=r["mapping_confidence"],
             evidence={"system_code": r.get("system_code")})

    # ---- zone load allocated to board / circuit ----
    for a in C.read_rows_csv(cfg.OUT_ELEC / "zone_load_to_board_allocation.csv"):
        w = _f(a.get("weight"))
        ev = {"category": a["load_category"], "method": a["mapping_method"]}
        edge(a["zone_id"], a["board_id"], "ZONE_LOAD_ALLOCATED_TO_BOARD", weight=w,
             source=SourceSystem.DERIVED, method=a["mapping_method"], confidence=a["mapping_confidence"],
             evidence=ev, notes=a["load_category"])
        edge(a["zone_id"], a["circuit_id"], "ZONE_LOAD_ALLOCATED_TO_CIRCUIT", weight=w,
             source=SourceSystem.DERIVED, method=a["mapping_method"], confidence=a["mapping_confidence"],
             evidence=ev, notes=a["load_category"])

    # ---- meters ----
    for m in gold.meter_names():
        mid = C.meter_id(m)
        add(C.Entity(mid, "Meter", m, eplus_name=m, source_system=SourceSystem.ENERGYPLUS,
                     source_file=cfg.IDF_FILE.name, value_class=ValueClass.ENERGYPLUS_SIMULATED,
                     confidence=Confidence.EXACT, properties={"meter_name": m}))
        edge(mid, bnode, "METER_MEASURES_ENTITY", source=SourceSystem.ENERGYPLUS,
             method="energyplus_meter", confidence=Confidence.EXACT)

    # ---- write graph (merge the Phase-8 HVAC subgraph if present) ----
    node_rows = [n.to_node_row() for n in nodes.values()]
    edge_rows = [e.to_row() for e in edges]
    seen = {r["node_id"] for r in node_rows}
    for r in C.read_rows_csv(cfg.OUT_KG / "hvac_nodes.csv"):
        if r.get("node_id") and r["node_id"] not in seen:
            node_rows.append(r)
            seen.add(r["node_id"])
    for r in C.read_rows_csv(cfg.OUT_KG / "hvac_energy_graph_edges.csv"):
        if r.get("relationship_type") not in ("", "NOTE"):
            edge_rows.append(r)
    C.write_rows_csv(cfg.OUT_KG / "graph_nodes.csv", node_rows, NODE_FIELDS)
    C.write_rows_csv(cfg.OUT_KG / "graph_edges.csv", edge_rows, EDGE_FIELDS)
    C.write_jsonl(cfg.OUT_KG / "graph_nodes.jsonl", node_rows)
    C.write_jsonl(cfg.OUT_KG / "graph_edges.jsonl", edge_rows)

    # electrical-subgraph mirror
    el_types = {"ElectricalBoard", "Circuit", "LightFixture", "Outlet", "Alarm", "CableTray"}
    el_rels = {"BOARD_SUPPLIES_CIRCUIT", "CIRCUIT_SUPPLIES_LOAD_POINT", "ZONE_LOAD_ALLOCATED_TO_BOARD",
               "ZONE_LOAD_ALLOCATED_TO_CIRCUIT", "OBJECT_LOCATED_ON_FLOOR", "OBJECT_ASSIGNED_TO_ZONE"}
    C.write_rows_csv(cfg.OUT_ELEC / "electrical_graph_nodes.csv",
                     [n.to_node_row() for n in nodes.values() if n.entity_type in el_types], NODE_FIELDS)
    C.write_rows_csv(cfg.OUT_ELEC / "electrical_graph_edges.csv",
                     [e.to_row() for e in edges if e.relationship_type in el_rels], EDGE_FIELDS)

    _schema_docs(node_rows, edge_rows)
    return {"nodes": len(node_rows), "edges": len(edge_rows)}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _schema_docs(node_rows, edge_rows) -> None:
    from collections import Counter
    nt = Counter(r["node_type"] for r in node_rows)
    et = Counter(r["relationship_type"] for r in edge_rows)
    schema = ["# Knowledge Graph Schema", "",
              f"Nodes: **{len(node_rows)}**, Edges: **{len(edge_rows)}**", "",
              "## Node types"] + [f"- `{k}`: {v}" for k, v in nt.most_common()] + \
             ["", "## Relationship types"] + [f"- `{k}`: {v}" for k, v in et.most_common()] + \
             ["", "Every node carries source_system/value_class/confidence; every edge carries "
              "source/method/confidence/evidence. Confidence ∈ {exact,high,medium,low,manual_review}.",
              "Boards are distribution assets and are never modelled as consuming loads."]
    C.write_text(cfg.OUT_KG / "graph_schema.md", "\n".join(schema))

    dd = [{"object": "node", "field": f, "description": d} for f, d in [
        ("node_id", "stable canonical id"), ("node_type", "entity type"),
        ("name", "human-readable name"), ("source_system", "originating system"),
        ("ifc_global_id", "IFC GlobalId when applicable"), ("eplus_name", "EnergyPlus name when applicable"),
        ("zone_id/floor_id/room_id", "spatial keys"), ("coordinates", "[x,y,z] metres when located"),
        ("properties_json", "typed properties"), ("value_class", "how the entity/value is justified"),
        ("confidence", "mapping confidence")]]
    dd += [{"object": "edge", "field": f, "description": d} for f, d in [
        ("edge_id", "stable id"), ("source_node_id/target_node_id", "endpoints"),
        ("relationship_type", "edge type"), ("direction", "directed/undirected"),
        ("weight", "allocation weight (0..1) where applicable"), ("source", "evidence origin"),
        ("method", "how the edge was derived"), ("confidence", "exact..manual_review"),
        ("evidence_json", "supporting evidence")]]
    C.write_rows_csv(cfg.OUT_KG / "graph_data_dictionary.csv", dd)


if __name__ == "__main__":
    print(run())

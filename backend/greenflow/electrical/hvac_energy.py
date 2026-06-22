"""Phase 8 — HVAC ↔ energy graph integration.

Connects the HVAC layer to the energy + electrical layers without ever claiming a
1:1 IFC↔EnergyPlus mapping. IFC HVAC terminal devices (air terminals, space
heaters, cooled beams) are located and linked to the zone they serve; the
EnergyPlus PTAC object is recorded as the *representative model* of a zone's HVAC,
and the HVAC load allocation to boards (pseudo HVAC circuit) is referenced.

The 342 MB HVAC IFC is opened best-effort; if that fails, the EnergyPlus-side
edges (PTAC → zone, weather → HVAC load) are still produced.
"""
from __future__ import annotations

import math

from greenflow.bim.ifc_geometry import building_storeys

from . import canonical as C
from . import config as cfg
from . import gold
from . import ifc_common as ic
from .provenance import Confidence, SourceSystem, ValueClass

NODE_FIELDS = ["node_id", "node_type", "name", "label", "source_system", "source_file",
               "ifc_global_id", "eplus_name", "xeokit_object_id", "zone_id", "floor_id",
               "room_id", "coordinates", "properties_json", "value_class", "confidence", "notes"]
EDGE_FIELDS = ["edge_id", "source_node_id", "target_node_id", "relationship_type", "direction",
               "weight", "source", "method", "confidence", "evidence_json", "notes"]

TERMINAL_CLASSES = ["IfcAirTerminal", "IfcSpaceHeater", "IfcCooledBeam", "IfcAirTerminalBox"]
PLANT_CLASSES = ["IfcFan", "IfcCoil", "IfcChiller", "IfcPump", "IfcUnitaryEquipment", "IfcBoiler"]


def _centroids_by_floor():
    """zone centroids grouped by floor (from spatial_map cache + zones.csv)."""
    zones = {z["ifc_global_id"]: z for z in C.read_rows_csv(cfg.OUT_MAPPING / "zones.csv")}
    out: dict[str, list] = {}
    for r in C.read_rows_csv(cfg.OUT_MAPPING / "space_centroids.csv"):
        zr = zones.get(r["guid"])
        if not zr:
            continue
        try:
            out.setdefault(zr["floor_id"], []).append(
                (zr["zone_id"], zr["room_id"], float(r["x"]), float(r["y"])))
        except (TypeError, ValueError):
            pass
    return out


def run() -> dict[str, int]:
    cfg.ensure_dirs()
    fidx = ic.FloorIndex(building_storeys(cfg.ARCH_IFC))
    by_floor = _centroids_by_floor()
    devices, nodes, edges = [], [], []

    def nearest_zone(floor, x, y):
        cands = by_floor.get(floor, [])
        if not cands or x is None or y is None:
            return None, None, None
        best, bd = None, 1e18
        for (zid, rid, sx, sy) in cands:
            d = math.dist((x, y), (sx, sy))
            if d < bd:
                best, bd = (zid, rid), d
        return (best[0], best[1], round(bd, 2)) if best else (None, None, None)

    n_terminal = n_served = 0
    try:
        f = ic.open_ifc(cfg.HVAC_IFC)
        scale = ic.unit_scale(f)
        for cls in TERMINAL_CLASSES + PLANT_CLASSES:
            terminal = cls in TERMINAL_CLASSES
            for e in ic.by_type(f, cls):
                typed, _raw = ic.canonical_props(e)
                storey = ic.storey_of(e)
                floor = fidx.resolve(storey, scale)
                fid = floor["floor_id"] if floor else ""
                x, y, z = ic.placement_xyz(e, scale)
                did = C.device_id(e.GlobalId)
                zid = rid = None
                dist = None
                if terminal:
                    n_terminal += 1
                    zid, rid, dist = nearest_zone(fid, x, y)
                devices.append({"device_id": did, "ifc_global_id": e.GlobalId, "name": e.Name or "",
                                "ifc_class": cls, "role": "terminal" if terminal else "plant",
                                "floor_id": fid, "served_zone_id": zid or "", "distance_m": dist,
                                "system_code": typed.get("system_code")})
                ent = C.Entity(did, "HVACDevice", e.Name or cls, label=cls, ifc_global_id=e.GlobalId,
                               floor_id=fid, zone_id=zid, room_id=rid, x=x, y=y, z=z,
                               source_system=SourceSystem.IFC_HVAC, source_file="HVAC_enriched.ifc",
                               value_class=ValueClass.IFC_DERIVED, confidence=Confidence.HIGH,
                               properties={"ifc_class": cls, "role": "terminal" if terminal else "plant",
                                           "system_code": typed.get("system_code")})
                nodes.append(ent.to_node_row())
                if terminal and zid:
                    n_served += 1
                    conf = Confidence.MEDIUM if (dist is not None and dist <= 6.0) else Confidence.LOW
                    edges.append(C.Edge(did, zid, "HVAC_DEVICE_SERVES_ZONE", source=SourceSystem.IFC_HVAC,
                                        method="floor+nearest_space_centroid", confidence=conf,
                                        evidence={"distance_m": dist}).to_row())
        hvac_opened = True
    except Exception as ex:  # noqa: BLE001 — 342 MB file may be heavy; degrade gracefully
        hvac_opened = False
        edges.append({"edge_id": "hvac_open_failed", "source_node_id": "", "target_node_id": "",
                      "relationship_type": "NOTE", "direction": "", "weight": "", "source": "hvac",
                      "method": "", "confidence": "", "evidence_json": "{}",
                      "notes": f"HVAC IFC not extracted: {type(ex).__name__}"})

    # ---- EnergyPlus-side HVAC edges (PTAC representative + weather context) ----
    idf_map = {r["eplus_zone_name"]: r for r in C.read_rows_csv(cfg.OUT_ENERGY / "idf_energy_mapping.csv")}
    zones = C.read_rows_csv(cfg.OUT_MAPPING / "zones.csv")
    weather_node = "weather_openmeteo_2025"
    nodes.append(C.Entity(weather_node, "WeatherTimeseries", "Open-Meteo 2025 (30-min)",
                          source_system=SourceSystem.OPENMETEO, source_file="final_weather_timeseries",
                          value_class=ValueClass.MEASURED, confidence=Confidence.EXACT).to_node_row())
    n_ptac = 0
    for z in zones:
        ez = z.get("eplus_zone_name")
        if not ez:
            continue
        ezid = C.eplus_zone_node_id(ez)
        ptac = (idf_map.get(ez) or {}).get("ptac_object_name")
        if ptac:
            n_ptac += 1
            pid = C.entity_id("ptac", ptac)
            nodes.append(C.Entity(pid, "PTAC", ptac, eplus_name=ptac, zone_id=z["zone_id"],
                                  floor_id=z["floor_id"], source_system=SourceSystem.ENERGYPLUS,
                                  source_file=cfg.IDF_FILE.name, value_class=ValueClass.ENERGYPLUS_SIMULATED,
                                  confidence=Confidence.EXACT,
                                  properties={"represents": "zone HVAC (fan+coil)"}).to_node_row())
            edges.append(C.Edge(pid, z["zone_id"], "ENERGYPLUS_PTAC_REPRESENTS_HVAC_FOR",
                                source=SourceSystem.ENERGYPLUS, method="idf_zone_ptac",
                                confidence=Confidence.EXACT,
                                evidence={"relationship": "representative_model"}).to_row())
        edges.append(C.Edge(z["zone_id"], ezid, "ZONE_HAS_HVAC_LOAD", source=SourceSystem.GREENFLOW_POST,
                            method="final_hvac_electricity_kw", confidence=Confidence.HIGH,
                            evidence={"value_class": ValueClass.ENERGYPLUS_SIMULATED}).to_row())
        edges.append(C.Edge(weather_node, z["zone_id"], "WEATHER_CONTEXT_FOR_HVAC_LOAD",
                            source=SourceSystem.OPENMETEO, method="weather_join", confidence=Confidence.HIGH,
                            evidence={}).to_row())

    C.write_rows_csv(cfg.OUT_MAPPING / "hvac_devices.csv", devices)
    C.write_rows_csv(cfg.OUT_KG / "hvac_nodes.csv", nodes, NODE_FIELDS)
    C.write_rows_csv(cfg.OUT_KG / "hvac_energy_graph_edges.csv", edges, EDGE_FIELDS)

    md = f"""# HVAC ↔ Energy Mapping Quality Report

- HVAC IFC extracted: **{hvac_opened}** ({cfg.HVAC_IFC.name})
- HVAC devices captured: **{len(devices)}** (terminals: {n_terminal}, served-zone links: {n_served})
- EnergyPlus PTAC representatives: **{n_ptac}** zones (relationship = `representative_model`)
- Zone HVAC load edges: one per zone (value class = EnergyPlus simulated)
- Weather context edges: Open-Meteo 2025 → each zone HVAC load

IFC HVAC fans/coils/PTAC are **not** asserted to map 1:1 to EnergyPlus PTAC/fan/coil;
the PTAC is recorded as a representative abstraction of each zone's HVAC. HVAC load
is allocated to a **pseudo HVAC circuit** on the floor's main board (see Phase 6).
"""
    C.write_text(cfg.OUT_KG / "hvac_energy_mapping_quality_report.md", md)
    return {"hvac_devices": len(devices), "hvac_nodes": len(nodes), "hvac_edges": len(edges),
            "ptac_representatives": n_ptac, "hvac_opened": int(hvac_opened)}


if __name__ == "__main__":
    print(run())

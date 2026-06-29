"""Phase 3 — spatial mapping against the ARCH master.

Canonical floors (ARCH storeys) and zones (308 IfcSpaces, joined to the gold
EnergyPlus zone_id by sanitised GlobalId) are emitted, then every electrical
object is located: floor via IFC storey containment (high), and room/zone via
nearest IfcSpace centroid on that floor (medium/low), else floor-only +
manual_review. Space centroids (from ARCH tessellation) are cached for fast reruns.
"""
from __future__ import annotations

import math

from greenflow.bim.ifc_geometry import building_storeys, space_records, tessellate

from . import canonical as C
from . import config as cfg
from . import gold
from . import ifc_common as ic
from .provenance import Confidence, SourceSystem, ValueClass
from ..energy_scope import classify_energy_scope

NEAR_M = 6.0     # within this -> medium (spatial)
FAR_M = 16.0     # within this -> low; beyond -> floor-only / manual_review


def _space_centroids() -> dict[str, tuple[float, float, float]]:
    """guid -> (x,y,z) metres, from ARCH IfcSpace tessellation (cached)."""
    cache = cfg.OUT_MAPPING / "space_centroids.csv"
    if cache.exists():
        out = {}
        for r in C.read_rows_csv(cache):
            try:
                out[r["guid"]] = (float(r["x"]), float(r["y"]), float(r["z"]))
            except (TypeError, ValueError):
                pass
        if out:
            return out
    res = tessellate(cfg.ARCH_IFC, only_spaces=True)
    rows, out = [], {}
    for el in res.elements:
        v = el.verts
        if not v:
            continue
        n = len(v) // 3
        cx = sum(v[0::3]) / n
        cy = sum(v[1::3]) / n
        cz = sum(v[2::3]) / n
        out[el.guid] = (cx, cy, cz)
        rows.append({"guid": el.guid, "x": round(cx, 3), "y": round(cy, 3), "z": round(cz, 3)})
    C.write_rows_csv(cache, rows)
    return out


def build_floors() -> list[dict]:
    floors = []
    for s in building_storeys(cfg.ARCH_IFC):
        floors.append({
            "floor_id": C.floor_id(s["name"]), "name": s["name"],
            "floor_index": s["floor_index"], "elevation_m": s["elevation_m"],
            "source_system": SourceSystem.IFC_ARCH, "value_class": ValueClass.IFC_DERIVED,
            "confidence": Confidence.EXACT,
        })
    return floors


def build_zones() -> list[dict]:
    fidx = ic.FloorIndex(building_storeys(cfg.ARCH_IFC))
    eplus = gold.zone_eplus_map()
    dims = {d["zone_id"]: d for d in gold.zone_dimensions()}
    zones = []
    for s in space_records(cfg.ARCH_IFC):
        zid = C.zone_id_from_guid(s["guid"])
        floor = fidx.by_name(s["storey"])
        dim = dims.get(zid, {})
        area = dim.get("area_m2") or s["area_m2"]
        volume = dim.get("volume_m3") or s["volume_m3"]
        label = s["long_name"] or s["number"] or ""
        scope = classify_energy_scope(
            label,
            area_m2=area,
            volume_m3=volume,
            height_m=dim.get("ceiling_height_m"),
        )
        zones.append({
            "zone_id": zid, "room_id": C.entity_id("room", s["guid"]),
            "ifc_global_id": s["guid"], "eplus_zone_name": eplus.get(zid, ""),
            "floor_id": floor["floor_id"] if floor else "", "storey": s["storey"],
            "room_type": s["room_type"], "long_name": s["long_name"], "number": s["number"],
            "area_m2": area, "volume_m3": volume,
            "usage_type": dim.get("usage_type") or "", "controllable": s.get("controllable"),
            "in_gold": zid in eplus,
            **scope.to_dict(),
            "source_system": SourceSystem.IFC_ARCH, "value_class": ValueClass.IFC_DERIVED,
            "confidence": Confidence.HIGH,
        })
    return zones


def run() -> dict[str, int]:
    cfg.ensure_dirs()
    floors = build_floors()
    zones = build_zones()
    C.write_rows_csv(cfg.OUT_MAPPING / "floors.csv", floors)
    C.write_rows_csv(cfg.OUT_MAPPING / "zones.csv", zones)

    centroids = _space_centroids()
    # space guid -> floor + zone, grouped by floor for nearest search
    zone_by_guid = {z["ifc_global_id"]: z for z in zones}
    by_floor: dict[str, list] = {}
    for guid, (x, y, z) in centroids.items():
        zr = zone_by_guid.get(guid)
        if not zr:
            continue
        by_floor.setdefault(zr["floor_id"], []).append((guid, x, y, z, zr))

    # gather all located electrical objects
    objs: list[dict] = []
    for path, otype, idcol in [
        (cfg.OUT_ELEC / "electrical_boards.csv", "ElectricalBoard", "board_id"),
        (cfg.OUT_ELEC / "electrical_load_points.csv", "LoadPoint", "load_point_id"),
        (cfg.OUT_ELEC / "electrical_cable_assets.csv", "CableAsset", "cable_id"),
    ]:
        for r in C.read_rows_csv(path):
            objs.append({"object_id": r[idcol], "object_type": otype,
                         "ifc_global_id": r["ifc_global_id"], "ifc_class": r["ifc_class"],
                         "floor_id": r.get("floor_id", ""),
                         "x": _f(r.get("x")), "y": _f(r.get("y")), "z": _f(r.get("z"))})

    rows = []
    stats = {"floor_high": 0, "zone_medium": 0, "zone_low": 0, "zone_manual_review": 0,
             "floor_missing": 0, "no_coords": 0}
    for o in objs:
        floor_id = o["floor_id"]
        zone_id = room_id = ""
        zconf = Confidence.MANUAL_REVIEW
        dist = None
        method = "ifc_storey_containment"
        if not floor_id:
            stats["floor_missing"] += 1
        else:
            stats["floor_high"] += 1
        if o["x"] is None or o["y"] is None:
            stats["no_coords"] += 1
            note = "no placement coordinates; floor-only"
        else:
            cands = by_floor.get(floor_id, [])
            best, bestd = None, 1e18
            for (guid, sx, sy, sz, zr) in cands:
                d = math.dist((o["x"], o["y"]), (sx, sy))
                if d < bestd:
                    best, bestd = zr, d
            if best is not None and bestd <= FAR_M:
                zone_id = best["zone_id"]
                room_id = best["room_id"]
                dist = round(bestd, 2)
                method = "ifc_storey_containment+nearest_space_centroid"
                zconf = Confidence.MEDIUM if bestd <= NEAR_M else Confidence.LOW
                stats["zone_medium" if zconf == Confidence.MEDIUM else "zone_low"] += 1
                note = ""
            else:
                stats["zone_manual_review"] += 1
                note = ("no space within %.0f m on floor" % FAR_M) if cands else "no spaces on floor"
        rows.append({
            "object_id": o["object_id"], "object_type": o["object_type"],
            "ifc_global_id": o["ifc_global_id"], "ifc_class": o["ifc_class"],
            "floor_id": floor_id, "floor_confidence": Confidence.HIGH if floor_id else Confidence.MANUAL_REVIEW,
            "room_id": room_id, "zone_id": zone_id,
            "eplus_zone_name": gold.zone_eplus_map().get(zone_id, ""),
            "mapping_method": method, "zone_confidence": zconf,
            "distance_m": dist, "value_class": ValueClass.SPATIALLY_INFERRED,
            "notes": note,
        })
    C.write_rows_csv(cfg.OUT_MAPPING / "object_to_floor_room_zone_map.csv", rows)

    # quality report + coordinate-frame diagnostic
    obj_xy = [(o["x"], o["y"]) for o in objs if o["x"] is not None]
    cen_xy = [(x, y) for (_, x, y, _z) in
              [(g, *c) for g, c in centroids.items()]]
    _report(floors, zones, rows, stats, obj_xy, cen_xy)
    return {"floors": len(floors), "zones": len(zones),
            "objects_mapped": len(rows), **stats}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0.0


def _report(floors, zones, rows, stats, obj_xy, cen_xy) -> None:
    om = _med([abs(x) for x, _ in obj_xy] + [abs(y) for _, y in obj_xy])
    cm = _med([abs(x) for x, _ in cen_xy] + [abs(y) for _, y in cen_xy])
    frame = "aligned"
    if om and cm and (om / cm > 50 or cm / om > 50):
        frame = "POSSIBLE SCALE/ORIGIN MISMATCH"
    zones_in_gold = sum(1 for z in zones if z["in_gold"])
    lines = [
        "# Spatial Mapping Quality Report", "",
        f"- Canonical floors (ARCH storeys): **{len(floors)}**",
        f"- Zones (IfcSpace): **{len(zones)}**, joined to gold EnergyPlus zone_id: **{zones_in_gold}**",
        f"- Electrical objects located: **{len(rows)}**", "",
        "## Floor assignment (IFC storey containment)",
        f"- with floor (high confidence): **{stats['floor_high']}**",
        f"- floor unresolved: **{stats['floor_missing']}**", "",
        "## Zone assignment (nearest IfcSpace centroid, same floor)",
        f"- medium (≤{NEAR_M:.0f} m): **{stats['zone_medium']}**",
        f"- low (≤{FAR_M:.0f} m): **{stats['zone_low']}**",
        f"- manual_review (no nearby space / no coords): "
        f"**{stats['zone_manual_review'] + stats['no_coords']}**", "",
        "## Coordinate-frame diagnostic",
        f"- median |xy| electrical objects: {om:.1f} m; ARCH space centroids: {cm:.1f} m → **{frame}**",
        "",
        "Floor is the reliable spatial key (storey containment); zone-per-object is",
        "best-effort and is **not** required for board allocation, which works at",
        "floor + system-code + category level.",
    ]
    C.write_text(cfg.OUT_MAPPING / "spatial_mapping_quality_report.md", "\n".join(lines))


if __name__ == "__main__":
    print(run())

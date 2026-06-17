"""Tessellate enriched IFC files into web 3D layer objects.

Uses ifcopenshell's geometry iterator (world coordinates, already in metres)
which resolves IfcLocalPlacement recursion correctly — avoiding the placement
bugs REPO_BUILD_SPEC §5.2 warns about.

Design choices for a clean, light viewer:
- A single shared transform (recenter on the ARCH building bbox, drop to the
  ground, EnergyPlus/IFC Z-up -> glTF Y-up) is applied to every discipline so
  they overlay correctly.
- IfcSpace -> one object per space (individually pickable, the heatmap target).
- Every other discipline -> merged into ONE object per building storey, with a
  discipline theme colour. This keeps object/triangle counts low (tens of
  objects instead of tens of thousands) and the XKT small, while looking clean
  and professional.
- HVAC is class-filtered (air distribution + equipment only) before
  tessellation so the 350 MB pipe network does not blow up the asset.

Output object shape matches what bim.idf_to_gltf.write_glb consumes:
{id, name, entity_type, layer, zone_key, floor_key, color, opacity,
 positions(glTF flat), indices, properties}
"""

from __future__ import annotations

import multiprocessing
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ifc_element

from .idf_to_gltf import _to_gltf_coords

Vec = tuple[float, float, float]

# ---------------------------------------------------------------------------
# Layer themes (discipline -> base colour / opacity). Clean SaaS palette.
# ---------------------------------------------------------------------------
LAYER_THEME: dict[str, dict[str, Any]] = {
    "architecture": {"color": [0.86, 0.87, 0.89], "opacity": 1.0},
    "spaces": {"color": [0.06, 0.46, 0.43], "opacity": 0.32},
    "fenestration": {"color": [0.48, 0.71, 0.86], "opacity": 0.42},
    "structural": {"color": [0.62, 0.64, 0.68], "opacity": 1.0},
    "hvac": {"color": [0.20, 0.55, 0.78], "opacity": 0.95},
    "electrical": {"color": [0.92, 0.66, 0.20], "opacity": 0.95},
}

# Per-discipline IFC class filters (applied before tessellation).
# Architecture shell. Excluded for triangle budget:
#  - IfcMember (~10k curtain-wall mullions)
#  - IfcDoor (269 doors carry ~1.4M tris of handle/frame detail!)
#  - structural columns/beams (live in the STRUCT file, avoids duplication)
ARCH_SHELL_CLASSES = {
    "IfcWall", "IfcWallStandardCase", "IfcSlab", "IfcRoof", "IfcCovering",
    "IfcCurtainWall", "IfcPlate", "IfcStair", "IfcStairFlight", "IfcRailing",
}
HVAC_CLASSES = {
    "IfcDuctSegment", "IfcDuctFitting", "IfcAirTerminal", "IfcCooledBeam",
    "IfcSpaceHeater", "IfcDuctSilencer", "IfcFan", "IfcAirTerminalBox",
}
# Everything with geometry in the ELE / STRUCT files belongs to that layer.

ROOM_TYPE_MAP = {
    "OFFICE": "office", "OPEN OFFICE": "open_office", "MEETING": "meeting_room",
    "MEETING ROOM": "meeting_room", "BREAK ROOM": "amenity", "GYM": "amenity",
    "KITCHEN": "amenity", "LOBBY": "lobby", "CORRIDOR": "hallway",
    "STAIRCASE": "circulation", "SHELTER": "utility", "LOCKER ROOM": "amenity",
    "WASHING ROOM": "utility", "TECHNICAL": "utility", "STORAGE": "utility",
    "WC": "utility", "TOILET": "utility",
}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_") or "x"


def guid_to_id(guid: str) -> str:
    """Stable object id from an IFC GlobalId — preserves case (GlobalIds are
    case-sensitive base64) so 3D object ids never collide; only '$' -> '_'."""
    return "zone_" + re.sub(r"[^A-Za-z0-9_]", "_", guid or "x")


@dataclass
class RawElement:
    guid: str
    name: str
    ifc_class: str
    storey: str
    long_name: str           # for spaces: room type label
    verts: list[float]       # flat world metres (x,y,z,...)
    faces: list[int]         # flat triangle indices
    color: list[float] | None


@dataclass
class TessResult:
    elements: list[RawElement] = field(default_factory=list)
    bbox: list[float] = field(default_factory=lambda: [1e18, 1e18, 1e18, -1e18, -1e18, -1e18])


def _settings() -> ifcopenshell.geom.settings:
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    s.set("weld-vertices", True)
    return s


def tessellate(path: str | Path, *, include_classes: set[str] | None = None,
               only_spaces: bool = False) -> TessResult:
    """Tessellate a file's products (optionally class-filtered)."""
    f = ifcopenshell.open(str(path))
    if only_spaces:
        products = f.by_type("IfcSpace")
    elif include_classes is not None:
        products = [p for c in include_classes for p in f.by_type(c)]
    else:
        products = [p for p in f.by_type("IfcProduct")
                    if p.Representation is not None
                    and not p.is_a("IfcSpace")
                    and not p.is_a("IfcOpeningElement")]
    if not products:
        return TessResult()

    settings = _settings()
    nthreads = max(1, min(8, multiprocessing.cpu_count()))
    result = TessResult()
    try:
        it = ifcopenshell.geom.iterator(settings, f, nthreads, include=products)
    except TypeError:
        it = ifcopenshell.geom.iterator(settings, f, nthreads)
    if not it.initialize():
        return result

    storey_cache: dict[int, str] = {}
    while True:
        shape = it.get()
        verts = list(shape.geometry.verts)
        faces = list(shape.geometry.faces)
        if verts and faces:
            for i in range(0, len(verts), 3):
                for k in range(3):
                    result.bbox[k] = min(result.bbox[k], verts[i + k])
                    result.bbox[3 + k] = max(result.bbox[3 + k], verts[i + k])
            product = f.by_id(shape.id)
            result.elements.append(RawElement(
                guid=getattr(shape, "guid", "") or product.GlobalId,
                name=shape.name or product.Name or shape.type,
                ifc_class=shape.type,
                storey=_storey_of(product, storey_cache),
                long_name=(getattr(product, "LongName", "") or "")
                if product.is_a("IfcSpace") else "",
                verts=verts, faces=faces,
                color=_first_color(shape),
            ))
        if not it.next():
            break
    return result


def _storey_of(product, cache: dict[int, str]) -> str:
    key = product.id()
    if key in cache:
        return cache[key]
    storey = "building"
    try:
        # spaces are aggregated under storeys (IfcRelAggregates); elements are
        # contained (IfcRelContainedInSpatialStructure). Try both, walk up.
        node = ifc_element.get_aggregate(product) or ifc_element.get_container(product)
        hops = 0
        while node is not None and not node.is_a("IfcBuildingStorey") and hops < 8:
            node = ifc_element.get_aggregate(node) or ifc_element.get_container(node)
            hops += 1
        if node is not None and node.is_a("IfcBuildingStorey"):
            storey = node.Name or "building"
    except Exception:
        pass
    cache[key] = storey
    return storey


def _first_color(shape) -> list[float] | None:
    try:
        mats = shape.geometry.materials
        if mats and getattr(mats[0], "has_diffuse", False):
            d = mats[0].diffuse
            return [round(float(d[0]), 3), round(float(d[1]), 3), round(float(d[2]), 3)]
    except Exception:
        pass
    return None


def compute_origin(bbox: list[float]) -> tuple[float, float, float]:
    """Shared recentre: XY centre, Z to ground (min z)."""
    cx = (bbox[0] + bbox[3]) / 2.0
    cy = (bbox[1] + bbox[4]) / 2.0
    minz = bbox[2]
    return cx, cy, minz


def _transform(verts: list[float], origin: tuple[float, float, float]) -> list[float]:
    cx, cy, minz = origin
    out: list[float] = []
    for i in range(0, len(verts), 3):
        gx, gy, gz = _to_gltf_coords((verts[i] - cx, verts[i + 1] - cy, verts[i + 2] - minz))
        out.extend((round(gx, 4), round(gy, 4), round(gz, 4)))
    return out


# ---------------------------------------------------------------------------
# Object emission
# ---------------------------------------------------------------------------

def emit_space_objects(res: TessResult, origin,
                       live_keys: set[str] | None = None) -> list[dict[str, Any]]:
    """One object per IfcSpace (pickable, individually keyed). Curated "live"
    zones (carrying telemetry) are highlighted; the rest are faint context."""
    live_keys = live_keys or set()
    objs = []
    for el in res.elements:
        room_type = _norm_room_type(el.long_name)
        key = guid_to_id(el.guid)
        live = key in live_keys
        objs.append({
            "id": key, "name": el.long_name.title() or el.name or "Space",
            "entity_type": "ThermalZone", "layer": "spaces",
            "zone_key": key, "floor_key": _slug(el.storey),
            "color": [0.05, 0.5, 0.46] if live else [0.55, 0.62, 0.66],
            "opacity": 0.42 if live else 0.16,
            "positions": _transform(el.verts, origin), "indices": el.faces,
            "properties": {"room_type": room_type, "ifc_guid": el.guid,
                           "storey": el.storey, "long_name": el.long_name,
                           "live": live},
        })
    return objs


def decimate_mesh(positions: list[float], indices: list[int],
                  cell: float) -> tuple[list[float], list[int]]:
    """Grid-snap vertex clustering: merge vertices within a `cell`-metre grid,
    drop degenerate/duplicate triangles. Cuts dense pre-tessellated curved
    geometry (ducts, light fixtures) by 5–10x while keeping the shape."""
    keymap: dict[tuple, int] = {}
    new_pos: list[float] = []
    remap = [0] * (len(positions) // 3)
    for vi in range(len(positions) // 3):
        x, y, z = positions[vi * 3:vi * 3 + 3]
        key = (round(x / cell), round(y / cell), round(z / cell))
        idx = keymap.get(key)
        if idx is None:
            idx = len(new_pos) // 3
            keymap[key] = idx
            new_pos.extend((x, y, z))
        remap[vi] = idx
    new_idx: list[int] = []
    seen: set[tuple] = set()
    for t in range(0, len(indices), 3):
        a, b, c = remap[indices[t]], remap[indices[t + 1]], remap[indices[t + 2]]
        if a == b or b == c or a == c:
            continue
        k = (a, b, c) if a < b and a < c else (b, c, a) if b < a and b < c else (c, a, b)
        if k in seen:
            continue
        seen.add(k)
        new_idx.extend((a, b, c))
    return new_pos, new_idx


def emit_merged_objects(res: TessResult, origin, layer: str, entity_type: str,
                        cell: float | None = None) -> list[dict[str, Any]]:
    """Merge a discipline's elements into one object per storey.

    `cell` enables grid-snap decimation (metres) for heavy curved disciplines.
    """
    theme = LAYER_THEME[layer]
    by_storey: dict[str, dict[str, list]] = {}
    for el in res.elements:
        bucket = by_storey.setdefault(el.storey, {"pos": [], "idx": [], "n": 0})
        base = len(bucket["pos"]) // 3
        bucket["pos"].extend(_transform(el.verts, origin))
        bucket["idx"].extend(i + base for i in el.faces)
        bucket["n"] += 1
    objs = []
    for storey, bucket in by_storey.items():
        pos, idx = bucket["pos"], bucket["idx"]
        if not idx:
            continue
        if cell:
            pos, idx = decimate_mesh(pos, idx, cell)
        objs.append({
            "id": f"{layer}_{_slug(storey)}",
            "name": f"{layer.title()} · {storey}",
            "entity_type": entity_type, "layer": layer,
            "zone_key": None, "floor_key": _slug(storey),
            "color": theme["color"], "opacity": theme["opacity"],
            "positions": pos, "indices": idx,
            "properties": {"storey": storey, "element_count": bucket["n"]},
        })
    return objs


def building_storeys(arch_path: str | Path) -> list[dict[str, Any]]:
    """Ordered storeys from the ARCH file with elevations (metres)."""
    f = ifcopenshell.open(str(arch_path))
    out = []
    for s in f.by_type("IfcBuildingStorey"):
        elev = 0.0
        try:
            elev = float(s.Elevation or 0.0) / 1000.0  # storey Elevation is mm
        except Exception:
            pass
        out.append({"name": s.Name or "Level", "elevation_m": round(elev, 2),
                    "guid": s.GlobalId})
    out.sort(key=lambda x: x["elevation_m"])
    for i, s in enumerate(out):
        s["floor_index"] = i
        s["entity_key"] = _slug(s["name"])
    return out


def space_records(arch_path: str | Path) -> list[dict[str, Any]]:
    """All IfcSpace metadata (area/volume/room_type/storey/enriched GreenFlow
    fields) without geometry. The files are pre-enriched with a
    Pset_GreenFlow_Metadata carrying floor/zone/room-type/controllability."""
    f = ifcopenshell.open(str(arch_path))
    storey_cache: dict[int, str] = {}
    records = []
    for sp in f.by_type("IfcSpace"):
        psets = ifc_element.get_psets(sp)
        qto = {}
        for name, vals in psets.items():
            if "Qto" in name or "Quantities" in name:
                qto.update(vals)
        gf = psets.get("Pset_GreenFlow_Metadata", {})

        # Qto Height is in mm, volume in m³ (Revit mixed units).
        height_mm = _num(qto.get("Height"))
        volume = _num(qto.get("NetVolume") or qto.get("GrossVolume"))
        height_m = round(height_mm / 1000.0, 2) if height_mm else 3.2
        area = _num(qto.get("NetFloorArea") or qto.get("GrossFloorArea"))
        if not area and volume and height_m:
            area = volume / height_m

        long_name = (sp.LongName or "").strip()
        # LongName ("OPEN OFFICE", "MEETING") is richer than the generic
        # enriched subtype ("office"); prefer it, fall back to the subtype.
        room_type = _norm_room_type(long_name) if long_name \
            else (gf.get("GreenFlow_Device_Subtype") or "office")
        storey = (gf.get("GreenFlow_Floor_Name") or "").strip() \
            or _storey_of(sp, storey_cache)
        records.append({
            "guid": sp.GlobalId,
            "number": sp.Name or "",
            "long_name": long_name,
            "room_type": _norm_room_type(room_type),
            "storey": storey,
            "area_m2": round(area, 2) if area else None,
            "volume_m3": round(volume, 2) if volume else None,
            "height_m": height_m,
            "zone_name": gf.get("GreenFlow_Zone_Name", ""),
            "controllable": str(gf.get("GreenFlow_Controllable", "")).lower() == "true",
            "risk_level": (gf.get("GreenFlow_Risk_Level") or "normal").lower(),
        })
    return records


def _norm_room_type(rt: str) -> str:
    """Normalise enriched/LongName room types to the simulation room_type set."""
    rt = (rt or "").strip().lower()
    alias = {
        "open office": "open_office", "openoffice": "open_office",
        "meeting": "meeting_room", "meeting room": "meeting_room",
        "break room": "amenity", "gym": "amenity", "kitchen": "amenity",
        "locker room": "amenity", "corridor": "hallway", "staircase": "circulation",
        "washing room": "utility", "wc": "utility", "toilet": "utility",
        "technical": "utility", "storage": "utility", "shelter": "utility",
    }
    if rt in alias:
        return alias[rt]
    if rt in ROOM_LOADS_KEYS:
        return rt
    return alias.get(rt, rt if rt in ("office", "lobby", "amenity", "hallway",
                                      "circulation", "utility", "meeting_room",
                                      "open_office") else "office")


ROOM_LOADS_KEYS = {"open_office", "office", "meeting_room", "lobby", "amenity",
                   "hallway", "circulation", "utility"}


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Indexed GLB writer (smooth per-vertex normals; no 3x flat-normal expansion).
# Keeps assets small for large IFC buildings. One node/mesh per object,
# node.name = object id (so convert2xkt yields matching xeokit object ids).
# ---------------------------------------------------------------------------

import json as _json
import struct as _struct


def _smooth_normals(positions: list[float], indices: list[int]) -> list[float]:
    n = len(positions) // 3
    nx = [0.0] * n
    ny = [0.0] * n
    nz = [0.0] * n
    for t in range(0, len(indices), 3):
        a, b, c = indices[t], indices[t + 1], indices[t + 2]
        ax, ay, az = positions[a * 3:a * 3 + 3]
        bx, by, bz = positions[b * 3:b * 3 + 3]
        cx, cy, cz = positions[c * 3:c * 3 + 3]
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        fx, fy, fz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        for idx in (a, b, c):
            nx[idx] += fx
            ny[idx] += fy
            nz[idx] += fz
    out: list[float] = []
    for i in range(n):
        ln = (nx[i] ** 2 + ny[i] ** 2 + nz[i] ** 2) ** 0.5 or 1.0
        out.extend((round(nx[i] / ln, 4), round(ny[i] / ln, 4), round(nz[i] / ln, 4)))
    return out


def write_glb_indexed(objects: list[dict[str, Any]], out_path: str | Path) -> None:
    """Write objects as an indexed GLB with smooth normals."""
    bin_chunks: list[bytes] = []
    buffer_views: list[dict] = []
    accessors: list[dict] = []
    meshes: list[dict] = []
    nodes: list[dict] = []
    materials: list[dict] = []
    offset = 0

    def add_buffer(data: bytes, target: int) -> int:
        nonlocal offset
        pad = (4 - len(data) % 4) % 4
        data += b"\x00" * pad
        buffer_views.append({"buffer": 0, "byteOffset": offset,
                             "byteLength": len(data), "target": target})
        bin_chunks.append(data)
        offset += len(data)
        return len(buffer_views) - 1

    for obj in objects:
        pos = obj["positions"]
        idx = obj["indices"]
        if not pos or not idx:
            continue
        norm = _smooth_normals(pos, idx)
        pos_bv = add_buffer(_struct.pack(f"<{len(pos)}f", *pos), 34962)
        norm_bv = add_buffer(_struct.pack(f"<{len(norm)}f", *norm), 34962)
        idx_bv = add_buffer(_struct.pack(f"<{len(idx)}I", *idx), 34963)

        xs, ys, zs = pos[0::3], pos[1::3], pos[2::3]
        accessors.append({"bufferView": pos_bv, "componentType": 5126,
                          "count": len(pos) // 3, "type": "VEC3",
                          "min": [min(xs), min(ys), min(zs)],
                          "max": [max(xs), max(ys), max(zs)]})
        pos_acc = len(accessors) - 1
        accessors.append({"bufferView": norm_bv, "componentType": 5126,
                          "count": len(norm) // 3, "type": "VEC3"})
        norm_acc = len(accessors) - 1
        accessors.append({"bufferView": idx_bv, "componentType": 5125,
                          "count": len(idx), "type": "SCALAR"})
        idx_acc = len(accessors) - 1

        color = obj.get("color", [0.8, 0.8, 0.8])
        opacity = obj.get("opacity", 1.0)
        material: dict[str, Any] = {
            "name": f"mat_{obj['id']}",
            "pbrMetallicRoughness": {"baseColorFactor": [*color, opacity],
                                     "metallicFactor": 0.0, "roughnessFactor": 0.85},
            "doubleSided": True,
        }
        if opacity < 1.0:
            material["alphaMode"] = "BLEND"
        materials.append(material)
        meshes.append({"name": obj["id"], "primitives": [{
            "attributes": {"POSITION": pos_acc, "NORMAL": norm_acc},
            "indices": idx_acc, "material": len(materials) - 1}]})
        nodes.append({"name": obj["id"], "mesh": len(meshes) - 1})

    gltf = {
        "asset": {"version": "2.0", "generator": "greenflow-ifc"},
        "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes, "meshes": meshes, "materials": materials,
        "accessors": accessors, "bufferViews": buffer_views,
        "buffers": [{"byteLength": offset}],
    }
    json_bytes = _json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)
    bin_data = b"".join(bin_chunks)
    glb = b"glTF" + _struct.pack("<II", 2, 12 + 8 + len(json_bytes) + 8 + len(bin_data))
    glb += _struct.pack("<I", len(json_bytes)) + b"JSON" + json_bytes
    glb += _struct.pack("<I", len(bin_data)) + b"BIN\x00" + bin_data
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(glb)


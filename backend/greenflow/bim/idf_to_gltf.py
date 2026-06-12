"""Generate web 3D assets (GLB per layer + geometry.json) from a parsed IDF.

Layers produced from the archetype IDF:
  arch_shell    walls/roofs/floors as double-sided polygons
  spaces        per-zone extruded volumes (the click/heatmap targets)
  fenestration  window quads, offset slightly outward so they remain visible

Conventions:
  - Object id == entity_key (also the xeokit object id after XKT conversion).
  - EnergyPlus is Z-up; glTF is Y-up: (x, y, z) -> (x, z, -y).
  - GLB nodes carry the entity_key as node.name so convert2xkt produces
    matching xeokit object ids.
  - geometry.json carries the same triangles for the viewer's SceneModel
    fallback path (no XKT needed).
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

from .idf_parser import IdfModel
from .normalized import build_normalized

Vec3 = tuple[float, float, float]

LAYER_STYLE = {
    "arch_shell": {"color": [0.82, 0.84, 0.86], "opacity": 1.0},
    "spaces": {"color": [0.06, 0.46, 0.43], "opacity": 0.35},
    "fenestration": {"color": [0.45, 0.71, 0.86], "opacity": 0.45},
}

SURFACE_COLORS = {
    "wall": [0.85, 0.86, 0.88],
    "roof": [0.72, 0.74, 0.78],
    "ceiling": [0.80, 0.81, 0.84],
    "floor": [0.66, 0.68, 0.72],
}

ZONE_COLORS = {
    "open_office": [0.05, 0.46, 0.43],
    "office": [0.13, 0.55, 0.45],
    "meeting_room": [0.22, 0.47, 0.61],
    "amenity": [0.71, 0.55, 0.23],
    "hallway": [0.52, 0.55, 0.60],
}


# ---------------------------------------------------------------------------
# Triangulation (ear clipping on the dominant plane projection)
# ---------------------------------------------------------------------------

def _newell_normal(pts: list[Vec3]) -> Vec3:
    nx = ny = nz = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1, z1 = pts[i]
        x2, y2, z2 = pts[(i + 1) % n]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    length = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
    return (nx / length, ny / length, nz / length)


def _project_2d(pts: list[Vec3], normal: Vec3) -> list[tuple[float, float]]:
    ax, ay, az = (abs(c) for c in normal)
    if az >= ax and az >= ay:
        return [(p[0], p[1]) for p in pts]
    if ax >= ay:
        return [(p[1], p[2]) for p in pts]
    return [(p[0], p[2]) for p in pts]


def triangulate(pts: list[Vec3]) -> list[tuple[int, int, int]]:
    """Ear-clipping triangulation of a simple planar polygon."""
    n = len(pts)
    if n < 3:
        return []
    if n == 3:
        return [(0, 1, 2)]
    if n == 4:
        return [(0, 1, 2), (0, 2, 3)]

    normal = _newell_normal(pts)
    p2 = _project_2d(pts, normal)

    def cross(o, a, b):
        return (p2[a][0] - p2[o][0]) * (p2[b][1] - p2[o][1]) - \
               (p2[a][1] - p2[o][1]) * (p2[b][0] - p2[o][0])

    # ensure CCW winding in projection
    area = sum(p2[i][0] * p2[(i + 1) % n][1] - p2[(i + 1) % n][0] * p2[i][1] for i in range(n))
    indices = list(range(n)) if area > 0 else list(range(n - 1, -1, -1))

    def point_in_tri(p, a, b, c):
        d1 = (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])
        d2 = (p[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (p[1] - c[1])
        d3 = (p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])
        has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
        has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
        return not (has_neg and has_pos)

    tris: list[tuple[int, int, int]] = []
    guard = 0
    while len(indices) > 3 and guard < 1000:
        guard += 1
        ear_found = False
        for i in range(len(indices)):
            prev_i, cur, next_i = indices[i - 1], indices[i], indices[(i + 1) % len(indices)]
            if cross(prev_i, cur, next_i) <= 0:
                continue
            if any(point_in_tri(p2[j], p2[prev_i], p2[cur], p2[next_i])
                   for j in indices if j not in (prev_i, cur, next_i)):
                continue
            tris.append((prev_i, cur, next_i))
            indices.pop(i)
            ear_found = True
            break
        if not ear_found:  # degenerate polygon: fall back to fan
            break
    if len(indices) == 3:
        tris.append((indices[0], indices[1], indices[2]))
    elif len(indices) > 3:
        tris.extend((indices[0], indices[i], indices[i + 1]) for i in range(1, len(indices) - 1))
    return tris


# ---------------------------------------------------------------------------
# Mesh building
# ---------------------------------------------------------------------------

def _to_gltf_coords(v: Vec3) -> Vec3:
    """EnergyPlus Z-up -> glTF Y-up."""
    return (v[0], v[2], -v[1])


def polygon_to_mesh(pts: list[Vec3], offset: float = 0.0) -> tuple[list[float], list[int]]:
    """Triangulated (positions, indices) for a planar polygon, optionally
    offset along its normal. Positions are in glTF (Y-up) coordinates."""
    if offset:
        nx, ny, nz = _newell_normal(pts)
        pts = [(p[0] + nx * offset, p[1] + ny * offset, p[2] + nz * offset) for p in pts]
    tris = triangulate(pts)
    positions: list[float] = []
    for p in pts:
        positions.extend(round(c, 4) for c in _to_gltf_coords(p))
    indices = [i for tri in tris for i in tri]
    return positions, indices


def extruded_prism(footprint: list[tuple[float, float]], z0: float, z1: float
                   ) -> tuple[list[float], list[int]]:
    """Closed prism from a 2D footprint between z0 and z1 (glTF coords out)."""
    n = len(footprint)
    bottom = [(x, y, z0) for x, y in footprint]
    top = [(x, y, z1) for x, y in footprint]
    positions: list[float] = []
    for p in bottom + top:
        positions.extend(round(c, 4) for c in _to_gltf_coords(p))
    indices: list[int] = []
    for a, b, c in triangulate(bottom):
        indices.extend([a, c, b])              # bottom faces down
    for a, b, c in triangulate(top):
        indices.extend([n + a, n + b, n + c])  # top faces up
    for i in range(n):
        j = (i + 1) % n
        indices.extend([i, j, n + j, i, n + j, n + i])
    return positions, indices


# ---------------------------------------------------------------------------
# Build per-layer object lists
# ---------------------------------------------------------------------------

def build_layer_objects(model: IdfModel) -> dict[str, list[dict[str, Any]]]:
    norm = build_normalized(model)
    zone_room_type = {z["entity_key"]: z["room_type"] for z in norm["zones"]}

    layers: dict[str, list[dict[str, Any]]] = {"arch_shell": [], "spaces": [], "fenestration": []}

    for s in norm["surfaces"]:
        pts = [tuple(v) for v in s["vertices"]]
        positions, indices = polygon_to_mesh(pts)
        if not indices:
            continue
        layers["arch_shell"].append({
            "id": s["entity_key"],
            "name": s["name"],
            "entity_type": "Surface",
            "zone_key": s["zone_key"],
            "floor_key": "storey_0",
            "color": SURFACE_COLORS.get(s["surface_type"], [0.8, 0.8, 0.8]),
            "opacity": 1.0,
            "positions": positions,
            "indices": indices,
            "properties": {"surface_type": s["surface_type"],
                           "construction": s["construction"],
                           "boundary": s["boundary"]},
        })

    for f in norm["fenestrations"]:
        pts = [tuple(v) for v in f["vertices"]]
        positions, indices = polygon_to_mesh(pts, offset=0.04)
        if not indices:
            continue
        layers["fenestration"].append({
            "id": f["entity_key"],
            "name": f["name"],
            "entity_type": "Window",
            "zone_key": f["zone_key"],
            "floor_key": "storey_0",
            "color": [0.45, 0.71, 0.86],
            "opacity": 0.5,
            "positions": positions,
            "indices": indices,
            "properties": {"construction": f["construction"],
                           "base_surface": f["base_surface"]},
        })

    # Zone volumes: extrude each floor surface footprint of the zone.
    floor_surfaces: dict[str, list[list[Vec3]]] = {}
    for s in norm["surfaces"]:
        if s["surface_type"] == "floor":
            floor_surfaces.setdefault(s["zone_key"], []).append(
                [tuple(v) for v in s["vertices"]])
    zone_info = {z["entity_key"]: z for z in norm["zones"]}
    for zone_key, footprints in floor_surfaces.items():
        z = zone_info.get(zone_key)
        if not z:
            continue
        positions: list[float] = []
        indices: list[int] = []
        for fp in footprints:
            z_base = sum(p[2] for p in fp) / len(fp)
            fp2d = [(p[0], p[1]) for p in fp]
            pos, idx = extruded_prism(fp2d, z_base + 0.05, z_base + z["height_m"] - 0.05)
            base = len(positions) // 3
            positions.extend(pos)
            indices.extend(i + base for i in idx)
        layers["spaces"].append({
            "id": zone_key,
            "name": z["name"],
            "entity_type": "ThermalZone",
            "zone_key": zone_key,
            "floor_key": "storey_0",
            "color": ZONE_COLORS.get(zone_room_type.get(zone_key, ""), [0.06, 0.46, 0.43]),
            "opacity": 0.35,
            "positions": positions,
            "indices": indices,
            "properties": {"room_type": z["room_type"], "area_m2": z["area_m2"],
                           "volume_m3": z["volume_m3"]},
        })

    return layers


# ---------------------------------------------------------------------------
# GLB writer (minimal binary glTF 2.0)
# ---------------------------------------------------------------------------

def _compute_flat_normals(positions: list[float], indices: list[int]
                          ) -> tuple[list[float], list[float], list[int]]:
    """Expand indexed mesh to flat-shaded triangles (positions, normals, indices)."""
    out_pos: list[float] = []
    out_norm: list[float] = []
    out_idx: list[int] = []
    for t in range(0, len(indices), 3):
        ia, ib, ic = indices[t], indices[t + 1], indices[t + 2]
        a = positions[ia * 3: ia * 3 + 3]
        b = positions[ib * 3: ib * 3 + 3]
        c = positions[ic * 3: ic * 3 + 3]
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        ln = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
        nx, ny, nz = nx / ln, ny / ln, nz / ln
        base = len(out_pos) // 3
        out_pos.extend(a + b + c)
        out_norm.extend([nx, ny, nz] * 3)
        out_idx.extend([base, base + 1, base + 2])
    return out_pos, out_norm, out_idx


def write_glb(objects: list[dict[str, Any]], out_path: str | Path) -> None:
    """Write objects as a GLB: one node+mesh per object, node.name = object id."""
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
        pos, norm, idx = _compute_flat_normals(obj["positions"], obj["indices"])
        pos_bytes = struct.pack(f"<{len(pos)}f", *pos)
        norm_bytes = struct.pack(f"<{len(norm)}f", *norm)
        idx_bytes = struct.pack(f"<{len(idx)}I", *idx)

        pos_bv = add_buffer(pos_bytes, 34962)
        norm_bv = add_buffer(norm_bytes, 34962)
        idx_bv = add_buffer(idx_bytes, 34963)

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
        material = {
            "name": f"mat_{obj['id']}",
            "pbrMetallicRoughness": {
                "baseColorFactor": [*color, opacity],
                "metallicFactor": 0.0,
                "roughnessFactor": 0.9,
            },
            "doubleSided": True,
        }
        if opacity < 1.0:
            material["alphaMode"] = "BLEND"
        materials.append(material)

        meshes.append({"name": obj["id"], "primitives": [{
            "attributes": {"POSITION": pos_acc, "NORMAL": norm_acc},
            "indices": idx_acc,
            "material": len(materials) - 1,
        }]})
        nodes.append({"name": obj["id"], "mesh": len(meshes) - 1})

    gltf = {
        "asset": {"version": "2.0", "generator": "greenflow-idf-to-gltf"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": offset}],
    }

    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)
    bin_data = b"".join(bin_chunks)

    glb = b"glTF"
    glb += struct.pack("<II", 2, 12 + 8 + len(json_bytes) + 8 + len(bin_data))
    glb += struct.pack("<I", len(json_bytes)) + b"JSON" + json_bytes
    glb += struct.pack("<I", len(bin_data)) + b"BIN\x00" + bin_data

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(glb)

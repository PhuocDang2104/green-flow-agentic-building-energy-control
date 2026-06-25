"""Build 3D web assets from the enriched IFC building (replaces the IDF boxes).

Pipeline:
  enriched IFC (ARCH/ELE/HVAC/STRUCT)
  -> ifcopenshell tessellation (world coords, metres)
  -> shared recentre + Z-up->Y-up
  -> per-layer GLB (spaces = per-space objects; other disciplines merged/storey)
  -> XKT via tools/convert_xkt.mjs
  -> metadata / object_map / viewer-manifest / geometry.json fallback
  -> db/seed/normalized_building.json (via extract_ifc)

Offline only (needs ifcopenshell); outputs are committed so runtime/Docker
never need ifcopenshell.

Usage: python scripts/build_3d_assets_ifc.py [--skip-xkt]
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from greenflow.bim import ifc_geometry as G  # noqa: E402
from greenflow.bim.ifc_extractor import extract_ifc  # noqa: E402

BUILDING_KEY = "greenflow_archetype"
IFC_DIR = ROOT / "data" / "enriched_IFC"
ARCH = IFC_DIR / "ARCH_AsBuilt_enriched.ifc"
ELE = IFC_DIR / "ELE_enriched.ifc"
HVAC = IFC_DIR / "HVAC_enriched.ifc"
STRUCT = IFC_DIR / "STRUCTURAL_enriched.ifc"
ASSET_DIR = ROOT / "web" / "public" / "assets" / "buildings" / BUILDING_KEY
SEED_DIR = ROOT / "db" / "seed"

ENTITY_IFC_TYPE = {
    "ThermalZone": "IfcSpace", "Surface": "IfcWall", "Window": "IfcWindow",
    "StructuralElement": "IfcColumn", "HvacElement": "IfcDuctSegment",
    "ElectricalElement": "IfcFlowTerminal",
}

# layer -> (LAYER_LABELS key for the frontend, default_visible, pickable)
LAYER_META = {
    "architecture": ("architecture", True, False),
    "spaces": ("thermal_zones", True, True),
    "fenestration": ("fenestration", False, False),
    "structural": ("structural", False, False),
    "hvac": ("hvac", False, False),
    "electrical": ("electrical", False, False),
}


def _clean_old_assets() -> None:
    """Remove stale GLB/XKT/metadata from a previous (IDF or partial) build."""
    for sub in ("glb", "xkt", "metadata"):
        d = ASSET_DIR / sub
        if d.exists():
            for f in d.glob("*"):
                f.unlink()


def main(skip_xkt: bool = False) -> None:
    for sub in ("glb", "xkt", "geometry", "metadata", "mapping"):
        (ASSET_DIR / sub).mkdir(parents=True, exist_ok=True)
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    _clean_old_assets()

    # Curated live-zone keys (cheap: no geometry) to highlight in the viewer.
    normalized = extract_ifc(ARCH)
    live_keys = {z["entity_key"] for z in normalized["zones"]}
    print(f"[curate] {len(live_keys)} live zones", flush=True)

    # Origin first (ARCH shell bbox), shared by every layer.
    print(f"[origin] ARCH shell bbox ({ARCH.name}) ...", flush=True)
    arch = G.tessellate(ARCH, include_classes=G.ARCH_SHELL_CLASSES)
    origin = G.compute_origin(arch.bbox)
    print(f"         origin={tuple(round(x,1) for x in origin)} "
          f"elements={len(arch.elements)}", flush=True)

    object_map: list[dict] = []
    geometry_json: dict = {"building_key": BUILDING_KEY, "layers": {}}
    manifest_assets: list[dict] = []

    def process(layer: str, entity_type: str, objects: list) -> None:
        """Write one layer's GLB/metadata/object_map immediately (frees RAM)."""
        if not objects:
            print(f"      (skip empty layer {layer})", flush=True)
            return
        glb_path = ASSET_DIR / "glb" / f"{layer}.glb"
        G.write_glb_indexed(objects, glb_path)
        tris = sum(len(o["indices"]) // 3 for o in objects)
        print(f"      {layer}: {len(objects)} obj, {tris} tris, "
              f"{glb_path.stat().st_size // 1024} KB GLB", flush=True)
        meta = {
            "id": f"{BUILDING_KEY}_{layer}", "projectId": "greenflow",
            "metaObjects": [{"id": f"model_{layer}", "name": layer,
                             "type": "Default", "parent": None}] +
            [{"id": o["id"], "name": o["name"],
              "type": ENTITY_IFC_TYPE.get(o["entity_type"], "Default"),
              "parent": f"model_{layer}"} for o in objects],
        }
        (ASSET_DIR / "metadata" / f"{layer}_metadata.json").write_text(
            json.dumps(meta), encoding="utf-8")

        geometry_json["layers"][layer] = {
            "style": {"color": objects[0]["color"], "opacity": objects[0]["opacity"]},
            "objects": [{k: o[k] for k in ("id", "name", "entity_type", "zone_key",
                                           "floor_key", "color", "opacity",
                                           "positions", "indices", "properties")}
                        for o in objects],
        }
        for o in objects:
            object_map.append({
                "xeokit_object_id": o["id"], "entity_key": o["id"],
                "entity_type": o["entity_type"], "zone_key": o["zone_key"],
                "floor_key": o["floor_key"], "layer": layer, "name": o["name"],
                "live": bool(o.get("properties", {}).get("live")),
                "room_type": o.get("properties", {}).get("room_type"),
            })
        label, vis, pick = LAYER_META[layer]
        manifest_assets.append({
            "asset_id": layer, "layer": label, "model_id": f"model_{layer}",
            "src": f"/assets/buildings/{BUILDING_KEY}/xkt/{layer}.xkt",
            "glb_src": f"/assets/buildings/{BUILDING_KEY}/glb/{layer}.glb",
            "metadata_src": f"/assets/buildings/{BUILDING_KEY}/metadata/{layer}_metadata.json",
            "default_visible": vis, "pickable": pick,
        })

    # --- process layers one at a time (tessellate -> emit -> write -> free) ---
    process("architecture", "Surface",
            G.emit_merged_objects(arch, origin, "architecture", "Surface"))
    del arch

    print(f"[spaces] {ARCH.name} ...", flush=True)
    sp = G.tessellate(ARCH, only_spaces=True)
    process("spaces", "ThermalZone", G.emit_space_objects(sp, origin, live_keys))
    del sp

    print(f"[windows] {ARCH.name} ...", flush=True)
    win = G.tessellate(ARCH, include_classes={"IfcWindow"})
    process("fenestration", "Window",
            G.emit_merged_objects(win, origin, "fenestration", "Window"))
    del win

    print(f"[structural] {STRUCT.name} ...", flush=True)
    st = G.tessellate(STRUCT)
    process("structural", "StructuralElement",
            G.emit_merged_objects(st, origin, "structural", "StructuralElement",
                                  cell=0.2, material_color=True,
                                  class_palette=G.STRUCT_MATERIAL))
    del st

    # MEP geometry is dense pre-tessellated curves (ducts/fixtures) -> decimate.
    print(f"[electrical] {ELE.name} ...", flush=True)
    el = G.tessellate(ELE)
    process("electrical", "ElectricalElement",
            G.emit_merged_objects(el, origin, "electrical", "ElectricalElement",
                                  cell=0.08))
    del el

    print(f"[hvac] {HVAC.name} (filtered, may be slow) ...", flush=True)
    try:
        hv = G.tessellate(HVAC, include_classes=G.HVAC_CLASSES)
        process("hvac", "HvacElement",
                G.emit_merged_objects(hv, origin, "hvac", "HvacElement", cell=0.1))
        del hv
    except Exception as exc:   # never let HVAC kill the whole build
        print(f"      HVAC layer failed ({exc}); continuing without it", flush=True)

    (ASSET_DIR / "geometry" / "geometry.json").write_text(
        json.dumps(geometry_json), encoding="utf-8")
    (ASSET_DIR / "mapping" / "xeokit_object_map.json").write_text(
        json.dumps(object_map, indent=2), encoding="utf-8")

    # ---- normalized building JSON for the DB seed ----
    print("[seed] extract_ifc -> normalized_building.json ...")
    normalized = extract_ifc(ARCH)
    (SEED_DIR / "normalized_building.json").write_text(
        json.dumps(normalized, indent=2), encoding="utf-8")
    print(f"      live zones={normalized['building']['zone_count']} "
          f"devices={len(normalized['devices'])}")

    xkt_ok = convert_xkt() if not skip_xkt else False

    manifest = {
        "building_key": BUILDING_KEY, "building_name": normalized["building"]["name"],
        "viewer_stack": "xeokit", "geometry_format": "xkt" if xkt_ok else "geometry_json",
        "geometry_json_src": f"/assets/buildings/{BUILDING_KEY}/geometry/geometry.json",
        "object_map_src": f"/assets/buildings/{BUILDING_KEY}/mapping/xeokit_object_map.json",
        "assets": manifest_assets,
    }
    (ASSET_DIR / "viewer-manifest.json").write_text(json.dumps(manifest, indent=2),
                                                    encoding="utf-8")
    print(f"Done. geometry_format={manifest['geometry_format']}, "
          f"layers={[a['asset_id'] for a in manifest_assets]}")


def convert_xkt() -> bool:
    node = shutil.which("node")
    if not node:
        print("  node not found -> skip XKT (viewer uses geometry.json)")
        return False
    tools_dir = ROOT / "tools"
    if not (tools_dir / "node_modules" / "@xeokit").exists():
        print("  installing @xeokit/xeokit-convert ...")
        subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=tools_dir,
                       capture_output=True, text=True, shell=sys.platform == "win32")
    r = subprocess.run([node, str(tools_dir / "convert_xkt.mjs"), str(ASSET_DIR)],
                       capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print("  XKT conversion failed -> geometry.json fallback\n", r.stderr[-600:])
        return False
    return True


if __name__ == "__main__":
    main(skip_xkt="--skip-xkt" in sys.argv)

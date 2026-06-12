"""Build all 3D web assets from the archetype IDF.

Outputs (web/public/assets/buildings/greenflow_archetype/):
  glb/<layer>.glb            intermediate GLB (node.name = entity_key)
  xkt/<layer>.xkt            xeokit XKT (via tools/convert_xkt.mjs, if node available)
  geometry/geometry.json     raw triangles for the viewer's SceneModel fallback
  metadata/<layer>_metadata.json   xeokit metamodel per layer
  mapping/xeokit_object_map.json   object_id -> entity mapping
  viewer-manifest.json       what the frontend loads

Also writes db/seed/normalized_building.json consumed by scripts/seed_demo.py.

Usage: python scripts/build_3d_assets.py [--skip-xkt]
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from greenflow.bim.idf_parser import parse_idf  # noqa: E402
from greenflow.bim.idf_to_gltf import LAYER_STYLE, build_layer_objects, write_glb  # noqa: E402
from greenflow.bim.normalized import build_normalized  # noqa: E402

BUILDING_KEY = "greenflow_archetype"
IDF_PATH = ROOT / "data" / "greenflow_archetype.idf"
ASSET_DIR = ROOT / "web" / "public" / "assets" / "buildings" / BUILDING_KEY
SEED_DIR = ROOT / "db" / "seed"

ENTITY_IFC_TYPE = {
    "ThermalZone": "IfcSpace",
    "Surface": "IfcWall",
    "Window": "IfcWindow",
}

LAYER_LABELS = {
    "arch_shell": "architecture",
    "spaces": "thermal_zones",
    "fenestration": "fenestration",
}


def main(skip_xkt: bool = False) -> None:
    print(f"Parsing {IDF_PATH.name} ...")
    model = parse_idf(IDF_PATH)
    normalized = build_normalized(model, BUILDING_KEY)

    SEED_DIR.mkdir(parents=True, exist_ok=True)
    (SEED_DIR / "normalized_building.json").write_text(
        json.dumps(normalized, indent=2), encoding="utf-8")
    print(f"  zones={len(normalized['zones'])} surfaces={len(normalized['surfaces'])} "
          f"fenestrations={len(normalized['fenestrations'])} devices={len(normalized['devices'])}")

    layers = build_layer_objects(model)

    for sub in ("glb", "xkt", "geometry", "metadata", "mapping"):
        (ASSET_DIR / sub).mkdir(parents=True, exist_ok=True)

    object_map: list[dict] = []
    geometry_json: dict = {"building_key": BUILDING_KEY, "layers": {}}
    manifest_assets: list[dict] = []

    for layer_name, objects in layers.items():
        glb_path = ASSET_DIR / "glb" / f"{layer_name}.glb"
        write_glb(objects, glb_path)
        print(f"  wrote {glb_path.relative_to(ROOT)} ({len(objects)} objects, "
              f"{glb_path.stat().st_size // 1024} KB)")

        geometry_json["layers"][layer_name] = {
            "style": LAYER_STYLE.get(layer_name, {}),
            "objects": [{
                "id": o["id"], "name": o["name"], "entity_type": o["entity_type"],
                "zone_key": o["zone_key"], "floor_key": o["floor_key"],
                "color": o["color"], "opacity": o["opacity"],
                "positions": o["positions"], "indices": o["indices"],
                "properties": o["properties"],
            } for o in objects],
        }

        meta = {
            "id": f"{BUILDING_KEY}_{layer_name}",
            "projectId": "greenflow",
            "metaObjects": [
                {"id": f"model_{layer_name}", "name": layer_name,
                 "type": "Default", "parent": None},
                *[{
                    "id": o["id"], "name": o["name"],
                    "type": ENTITY_IFC_TYPE.get(o["entity_type"], "Default"),
                    "parent": f"model_{layer_name}",
                } for o in objects],
            ],
        }
        (ASSET_DIR / "metadata" / f"{layer_name}_metadata.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8")

        for o in objects:
            object_map.append({
                "xeokit_object_id": o["id"],
                "entity_key": o["id"],
                "entity_type": o["entity_type"],
                "zone_key": o["zone_key"],
                "floor_key": o["floor_key"],
                "layer": layer_name,
                "name": o["name"],
            })

        manifest_assets.append({
            "asset_id": layer_name,
            "layer": LAYER_LABELS.get(layer_name, layer_name),
            "model_id": f"model_{layer_name}",
            "src": f"/assets/buildings/{BUILDING_KEY}/xkt/{layer_name}.xkt",
            "glb_src": f"/assets/buildings/{BUILDING_KEY}/glb/{layer_name}.glb",
            "metadata_src": f"/assets/buildings/{BUILDING_KEY}/metadata/{layer_name}_metadata.json",
            "default_visible": layer_name != "fenestration",
            "pickable": layer_name == "spaces",
        })

    (ASSET_DIR / "geometry" / "geometry.json").write_text(
        json.dumps(geometry_json), encoding="utf-8")
    (ASSET_DIR / "mapping" / "xeokit_object_map.json").write_text(
        json.dumps(object_map, indent=2), encoding="utf-8")

    xkt_ok = False
    if not skip_xkt:
        xkt_ok = convert_xkt()

    manifest = {
        "building_key": BUILDING_KEY,
        "building_name": normalized["building"]["name"],
        "viewer_stack": "xeokit",
        "geometry_format": "xkt" if xkt_ok else "geometry_json",
        "geometry_json_src": f"/assets/buildings/{BUILDING_KEY}/geometry/geometry.json",
        "object_map_src": f"/assets/buildings/{BUILDING_KEY}/mapping/xeokit_object_map.json",
        "assets": manifest_assets,
    }
    (ASSET_DIR / "viewer-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  wrote viewer-manifest.json (geometry_format={manifest['geometry_format']})")


def convert_xkt() -> bool:
    """Run tools/convert_xkt.mjs for each GLB. Returns True if all converted."""
    node = shutil.which("node")
    if not node:
        print("  node not found -> skipping XKT conversion (viewer uses geometry.json)")
        return False
    tools_dir = ROOT / "tools"
    if not (tools_dir / "node_modules").exists():
        print("  installing tools dependencies (@xeokit/xeokit-convert) ...")
        r = subprocess.run(["npm", "install", "--no-audit", "--no-fund"],
                           cwd=tools_dir, capture_output=True, text=True, shell=sys.platform == "win32")
        if r.returncode != 0:
            print("  npm install failed -> skipping XKT conversion\n", r.stderr[-800:])
            return False
    r = subprocess.run([node, str(tools_dir / "convert_xkt.mjs"), str(ASSET_DIR)],
                       capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print("  XKT conversion failed -> viewer uses geometry.json fallback\n", r.stderr[-800:])
        return False
    return True


if __name__ == "__main__":
    main(skip_xkt="--skip-xkt" in sys.argv)

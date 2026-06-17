"""IFC extractor: enriched IFC -> normalized building dict.

Produces the same normalized contract as bim.normalized.build_normalized so the
whole downstream (3D assets, DB seed, simulation, agents) works unchanged.

The full building (308 spaces, 11 storeys) is rendered in 3D, but only a
curated subset of spaces become "live" thermal zones carrying telemetry and
agent actions — REPO_BUILD_SPEC §2.1 ("chọn 6–20 demo zones"). The remaining
spaces stay visible/pickable in the viewer (metadata-only).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from . import default_schedules as ds
from .ifc_geometry import building_storeys, guid_to_id, space_records
from .normalized import _build_devices_and_relations

BUILDING_KEY = "greenflow_archetype"

# Levels we curate live zones from (occupied office floors of the Nordic model).
CURATED_LEVELS = {"Level_01", "Level_02", "Level_03", "Level_04"}
MAX_CURATED_ZONES = 14
MIN_ZONE_AREA = 10.0


class IfcExtractorNotImplemented(NotImplementedError):
    pass


def extract_ifc(arch_ifc: str | Path,
                hvac_ifc: str | Path | None = None,
                ele_ifc: str | Path | None = None,
                building_key: str = BUILDING_KEY) -> dict[str, Any]:
    storeys = building_storeys(arch_ifc)
    spaces = space_records(arch_ifc)

    zones = _curate_zones(spaces)

    building = {
        "entity_key": building_key,
        "name": "Nordic LCA Office",
        "location_name": "Hanoi-Noi.Bai.Intl.AP",   # keep the demo weather/tariff story
        "latitude": 21.221,
        "longitude": 105.807,
        "timezone": "Asia/Ho_Chi_Minh",
        "building_type": "office",
        "source_dataset": "enriched_IFC (ARCH/ELE/HVAC/STRUCTURAL)",
        "total_area_m2": round(sum(z["area_m2"] for z in zones), 2),
        "zone_count": len(zones),
        "space_count": len(spaces),
        "storey_count": len(storeys),
    }

    floors = [{
        "entity_key": s["entity_key"], "name": s["name"],
        "floor_index": s["floor_index"], "elevation_m": s["elevation_m"],
    } for s in storeys]

    devices, relations = _build_devices_and_relations(zones, building_key)

    # spatial graph: building -> floors, floor -> zones
    relations.append({"src_type": "Building", "src_key": building_key,
                      "relation": "HAS_FLOOR", "dst_type": "Floor",
                      "dst_key": floors[0]["entity_key"] if floors else "",
                      "method": "ifc", "confidence": 1.0})
    for s in storeys:
        relations.append({"src_type": "Building", "src_key": building_key,
                          "relation": "HAS_FLOOR", "dst_type": "Floor",
                          "dst_key": s["entity_key"], "method": "ifc", "confidence": 1.0})
    for z in zones:
        relations.append({"src_type": "Floor", "src_key": z["floor_key"],
                          "relation": "HAS_ZONE", "dst_type": "Zone",
                          "dst_key": z["entity_key"], "method": "ifc", "confidence": 1.0})

    zone_equipment_map: dict[str, list[str]] = {}
    for d in devices:
        if d.get("zone_key"):
            zone_equipment_map.setdefault(d["zone_key"], []).append(d["entity_key"])

    return {
        "building": building,
        "floors": floors,
        "zones": zones,
        "surfaces": [],          # real geometry lives in the GLB/XKT layers
        "fenestrations": [],
        "constructions": [],
        "materials": [],
        "schedules": ds.SCHEDULES,
        "setpoints": {
            "cooling_schedule": "CoolSetSched",
            "heating_schedule": "HeatSetSched",
            "cooling_weekday": ds.SCHEDULES["CoolSetSched"]["weekday"],
            "heating_weekday": ds.SCHEDULES["HeatSetSched"]["weekday"],
        },
        "devices": devices,
        "zone_equipment_map": zone_equipment_map,
        "entity_relations": relations,
    }


def _curate_zones(spaces: list[dict]) -> list[dict]:
    """Pick a diverse, sensible set of live zones from the 308 IFC spaces."""
    candidates = [s for s in spaces
                  if s.get("area_m2") and s["area_m2"] >= MIN_ZONE_AREA]
    # prefer curated levels, then larger rooms, diverse room types
    preferred = [s for s in candidates if s["storey"] in CURATED_LEVELS]
    pool = preferred or candidates
    pool.sort(key=lambda s: (-(s["area_m2"] or 0)))

    chosen: list[dict] = []
    seen_types: dict[str, int] = {}
    for s in pool:
        rt = s["room_type"]
        if seen_types.get(rt, 0) >= 4:   # cap repeats of one room type
            continue
        seen_types[rt] = seen_types.get(rt, 0) + 1
        chosen.append(s)
        if len(chosen) >= MAX_CURATED_ZONES:
            break
    if not chosen:                       # fallback: take the biggest few
        chosen = pool[:MAX_CURATED_ZONES]

    zones = []
    for s in chosen:
        rt = s["room_type"]
        lights, equip, ppl = ds.loads_for(rt)
        area = s["area_m2"]
        height = round((s["volume_m3"] / area), 2) if s.get("volume_m3") and area else 3.2
        # estimate envelope/window from a square-ish footprint
        perimeter = 4.0 * math.sqrt(area)
        envelope = round(perimeter * height + area, 1)      # walls + roof-ish
        window = round(perimeter * height * 0.28, 1)        # ~28% glazing
        label = (s["long_name"].title() or "Space")
        zones.append({
            "entity_key": guid_to_id(s["guid"]),
            "name": f"{label} {s['number']}".strip(),
            "floor_key": _level_slug(s["storey"]),
            "room_type": rt,
            "comfort_profile": ds.comfort_profile_for(rt),
            "area_m2": area,
            "volume_m3": s.get("volume_m3") or round(area * height, 1),
            "height_m": height,
            "centroid": [0.0, 0.0, 0.0],
            "lights_w_m2": lights,
            "equip_w_m2": equip,
            "people_per_m2": ppl,
            "occupancy_schedule": "WorkHoursFrac",
            "lights_schedule": "WorkHoursFrac",
            "equip_schedule": "WorkHoursFrac",
            "window_area_m2": window,
            "envelope_area_m2": envelope,
            "source_space_name": f"{s['long_name']} {s['number']}".strip(),
            "ifc_guid": s["guid"],
            "storey": s["storey"],
        })
    return zones


def _level_slug(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_") or "building"

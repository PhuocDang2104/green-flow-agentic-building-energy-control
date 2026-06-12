"""Build normalized building JSON from a parsed IDF model.

Output mirrors the normalized-JSON contract in REPO_BUILD_SPEC §5.3, scoped to
what the IDF archetype contains. Devices are derived per zone (the IDF has no
MEP objects): one air terminal, one lighting circuit and one plug circuit per
zone, plus a building-level AHU and electrical board. These act as the
controllable action targets for the agent flow.
"""

from __future__ import annotations

import re
from typing import Any

from .idf_parser import IdfModel, zone_slug

ROOM_TYPE_MAP = {
    "open_office": "open_office",
    "office": "office",
    "meeting": "meeting_room",
    "amenity": "amenity",
    "circulation": "hallway",
}

COMFORT_PROFILE_MAP = {
    "open_office": "office_standard",
    "office": "office_standard",
    "meeting_room": "office_standard",
    "amenity": "relaxed",
    "hallway": "relaxed",
}


def _surface_slug(name: str) -> str:
    return "surface_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _fen_slug(name: str) -> str:
    return "window_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _room_type(zone_name: str) -> str:
    m = re.match(r"Block\s+(.+?)\s+Storey", zone_name, re.IGNORECASE)
    key = m.group(1).strip().lower().replace(" ", "_") if m else ""
    return ROOM_TYPE_MAP.get(key, "office")


def build_normalized(model: IdfModel, building_key: str = "greenflow_archetype") -> dict[str, Any]:
    building = {
        "entity_key": building_key,
        "name": model.building_name,
        "location_name": model.location_name,
        "latitude": model.latitude,
        "longitude": model.longitude,
        "timezone": "Asia/Ho_Chi_Minh",
        "building_type": "office",
        "source_dataset": "greenflow_archetype.idf",
        "total_area_m2": round(sum(z.area_m2 for z in model.zones.values()), 2),
        "zone_count": len(model.zones),
    }

    floors = [{
        "entity_key": "storey_0",
        "name": "Storey 0",
        "floor_index": 0,
        "elevation_m": 0.0,
    }]

    zones = []
    for z in model.zones.values():
        slug = zone_slug(z.name)
        room_type = _room_type(z.name)
        zones.append({
            "entity_key": f"zone_{slug}",
            "name": z.name,
            "floor_key": "storey_0",
            "room_type": room_type,
            "comfort_profile": COMFORT_PROFILE_MAP.get(room_type, "office_standard"),
            "area_m2": z.area_m2,
            "volume_m3": z.volume_m3,
            "height_m": z.height_m,
            "centroid": list(z.centroid),
            "lights_w_m2": z.lights_w_m2,
            "equip_w_m2": z.equip_w_m2,
            "people_per_m2": z.people_per_m2,
            "occupancy_schedule": z.occupancy_schedule,
            "lights_schedule": z.lights_schedule,
            "equip_schedule": z.equip_schedule,
            "source_space_name": z.name,
        })

    surfaces = [{
        "entity_key": _surface_slug(s.name),
        "name": s.name,
        "surface_type": s.surface_type,
        "construction": s.construction,
        "zone_key": f"zone_{zone_slug(s.zone_name)}",
        "boundary": s.boundary,
        "vertices": [list(v) for v in s.vertices],
    } for s in model.surfaces]

    base_surface_zone = {s.name: f"zone_{zone_slug(s.zone_name)}" for s in model.surfaces}
    fenestrations = [{
        "entity_key": _fen_slug(f.name),
        "name": f.name,
        "surface_type": f.surface_type,
        "construction": f.construction,
        "base_surface": f.base_surface,
        "zone_key": base_surface_zone.get(f.base_surface, ""),
        "vertices": [list(v) for v in f.vertices],
    } for f in model.fenestrations]

    devices, relations = _build_devices_and_relations(zones, building_key)

    zone_equipment_map = {}
    for d in devices:
        if d.get("zone_key"):
            zone_equipment_map.setdefault(d["zone_key"], []).append(d["entity_key"])

    return {
        "building": building,
        "floors": floors,
        "zones": zones,
        "surfaces": surfaces,
        "fenestrations": fenestrations,
        "constructions": [
            {"name": name, "layers": layers} for name, layers in model.constructions.items()
        ],
        "materials": [
            {"name": name, **info} for name, info in model.materials.items()
        ],
        "schedules": model.schedules,
        "setpoints": {
            "cooling_schedule": model.cooling_setpoint_schedule,
            "heating_schedule": model.heating_setpoint_schedule,
            "cooling_weekday": model.schedules.get(model.cooling_setpoint_schedule, {}).get("weekday"),
            "heating_weekday": model.schedules.get(model.heating_setpoint_schedule, {}).get("weekday"),
        },
        "devices": devices,
        "zone_equipment_map": zone_equipment_map,
        "entity_relations": relations,
    }


def _build_devices_and_relations(
    zones: list[dict], building_key: str
) -> tuple[list[dict], list[dict]]:
    devices: list[dict] = []
    relations: list[dict] = []

    for z in zones:
        slug = z["entity_key"].removeprefix("zone_")
        hvac_kw = round(z["area_m2"] * 0.09, 2)       # ~90 W/m2 cooling allowance
        light_kw = round(z["area_m2"] * z["lights_w_m2"] / 1000.0, 3)
        plug_kw = round(z["area_m2"] * z["equip_w_m2"] / 1000.0, 3)

        devices.append({
            "entity_key": f"airterminal_{slug}",
            "name": f"Air Terminal {z['name']}",
            "device_type": "hvac",
            "device_subtype": "air_terminal",
            "zone_key": z["entity_key"],
            "floor_key": z["floor_key"],
            "controllable": True,
            "risk_level": "normal",
            "nominal_power_kw": hvac_kw,
            "tag": f"AT-{slug}",
        })
        devices.append({
            "entity_key": f"lighting_{slug}",
            "name": f"Lighting Circuit {z['name']}",
            "device_type": "electrical",
            "device_subtype": "lighting_circuit",
            "zone_key": z["entity_key"],
            "floor_key": z["floor_key"],
            "controllable": True,
            "risk_level": "normal",
            "nominal_power_kw": light_kw,
            "tag": f"LT-{slug}",
        })
        devices.append({
            "entity_key": f"plug_{slug}",
            "name": f"Plug Circuit {z['name']}",
            "device_type": "electrical",
            "device_subtype": "plug_circuit",
            "zone_key": z["entity_key"],
            "floor_key": z["floor_key"],
            "controllable": False,
            "risk_level": "normal",
            "nominal_power_kw": plug_kw,
            "tag": f"PL-{slug}",
        })

        relations.append({
            "src_type": "Device", "src_key": f"airterminal_{slug}",
            "relation": "SUPPLIES_AIR_TO",
            "dst_type": "Zone", "dst_key": z["entity_key"],
            "method": "derived_from_idf_zone", "confidence": 1.0,
        })
        for dev_prefix in ("airterminal", "lighting", "plug"):
            relations.append({
                "src_type": "Device", "src_key": f"{dev_prefix}_{slug}",
                "relation": "LOCATED_IN",
                "dst_type": "Zone", "dst_key": z["entity_key"],
                "method": "derived_from_idf_zone", "confidence": 1.0,
            })
        relations.append({
            "src_type": "Floor", "src_key": "storey_0",
            "relation": "HAS_ZONE",
            "dst_type": "Zone", "dst_key": z["entity_key"],
            "method": "idf", "confidence": 1.0,
        })

    devices.append({
        "entity_key": "ahu_building_01",
        "name": "AHU Building 01",
        "device_type": "hvac",
        "device_subtype": "ahu",
        "zone_key": None,
        "floor_key": "storey_0",
        "controllable": True,
        "risk_level": "watch",
        "nominal_power_kw": 25.0,
        "tag": "AHU-01",
    })
    devices.append({
        "entity_key": "board_building_01",
        "name": "Main Electrical Board",
        "device_type": "electrical",
        "device_subtype": "distribution_board",
        "zone_key": None,
        "floor_key": "storey_0",
        "controllable": False,
        "risk_level": "critical",
        "nominal_power_kw": 60.0,
        "tag": "DB-01",
    })

    relations.append({
        "src_type": "Building", "src_key": building_key,
        "relation": "HAS_FLOOR",
        "dst_type": "Floor", "dst_key": "storey_0",
        "method": "idf", "confidence": 1.0,
    })
    for z in zones:
        slug = z["entity_key"].removeprefix("zone_")
        relations.append({
            "src_type": "Device", "src_key": "ahu_building_01",
            "relation": "SERVES",
            "dst_type": "Device", "dst_key": f"airterminal_{slug}",
            "method": "derived", "confidence": 0.9,
        })

    return devices, relations

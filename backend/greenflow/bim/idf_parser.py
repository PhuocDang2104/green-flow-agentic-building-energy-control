"""Parse an EnergyPlus IDF file into plain-Python structures.

Dependency-free parser tailored to the subset of objects used by the
GreenFlow archetype model (geometry, zones, internal loads, schedules,
constructions). Coordinates in the archetype are Relative with all zone
origins at (0,0,0), so surface vertices are effectively world coordinates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Low-level tokenizer
# ---------------------------------------------------------------------------

def read_idf_objects(path: str | Path) -> list[list[str]]:
    """Return a list of IDF objects, each a list of raw field strings.

    The first field is the object class name (upper-cased).
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    # Strip comments: everything from '!' to end of line.
    lines = [re.sub(r"!.*$", "", line) for line in text.splitlines()]
    blob = "\n".join(lines)

    objects: list[list[str]] = []
    for raw_obj in blob.split(";"):
        fields = [f.strip() for f in raw_obj.split(",")]
        # Drop leading empties caused by blank lines between objects.
        while fields and fields[0] == "":
            fields.pop(0)
        if not fields:
            continue
        fields[0] = fields[0].upper()
        objects.append(fields)
    return objects


def _num(value: str, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class IdfZone:
    name: str
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    area_m2: float = 0.0
    volume_m3: float = 0.0
    height_m: float = 0.0
    centroid: tuple[float, float, float] = (0.0, 0.0, 0.0)
    lights_w_m2: float = 0.0
    equip_w_m2: float = 0.0
    people_per_m2: float = 0.0
    lights_schedule: str = ""
    equip_schedule: str = ""
    occupancy_schedule: str = ""


@dataclass
class IdfSurface:
    name: str
    surface_type: str            # wall | floor | roof | ceiling
    construction: str
    zone_name: str
    boundary: str                # outdoors | ground | surface | adiabatic
    vertices: list[tuple[float, float, float]] = field(default_factory=list)


@dataclass
class IdfFenestration:
    name: str
    surface_type: str            # window | door | glassdoor
    construction: str
    base_surface: str
    vertices: list[tuple[float, float, float]] = field(default_factory=list)


@dataclass
class IdfModel:
    building_name: str = "Building"
    location_name: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    timezone_offset: float = 7.0
    zones: dict[str, IdfZone] = field(default_factory=dict)
    surfaces: list[IdfSurface] = field(default_factory=list)
    fenestrations: list[IdfFenestration] = field(default_factory=list)
    constructions: dict[str, list[str]] = field(default_factory=dict)
    materials: dict[str, dict] = field(default_factory=dict)
    schedules: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    cooling_setpoint_schedule: str = ""
    heating_setpoint_schedule: str = ""


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _polygon_area_2d(points: list[tuple[float, float]]) -> float:
    """Shoelace area of a 2D polygon."""
    n = len(points)
    s = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _parse_vertices(fields: list[str]) -> list[tuple[float, float, float]]:
    coords = [(_num(f) or 0.0) for f in fields]
    return [tuple(coords[i:i + 3]) for i in range(0, len(coords) - len(coords) % 3, 3)]


# ---------------------------------------------------------------------------
# Schedule:Compact parsing
# ---------------------------------------------------------------------------

_WEEKDAY_KEYS = ("weekday", "summerdesignday", "winterdesignday")


def parse_compact_schedule(fields: list[str]) -> dict[str, list[float]]:
    """Convert a Schedule:Compact body into hourly arrays.

    Returns {"weekday": [24 floats], "weekend": [24 floats]}.
    Handles the Through/For/Until structure used in the archetype file.
    Each "Until: HH:MM, value" fills hours from the previous Until in the
    same For: block up to HH.
    """
    weekday = [0.0] * 24
    weekend = [0.0] * 24
    targets: list[list[float]] = []
    cursor = 0
    i = 0
    while i < len(fields):
        low = fields[i].strip().lower()
        if low.startswith("for:"):
            days = low.replace("for:", "").split()
            targets = []
            if any(k in d for d in days for k in _WEEKDAY_KEYS) or "alldays" in days:
                targets.append(weekday)
            if any(d in ("alldays", "allotherdays", "weekends", "saturday", "sunday", "holiday")
                   for d in days):
                targets.append(weekend)
            cursor = 0
        elif low.startswith("until:"):
            hour = min(int(low.split(":", 2)[1].strip() or 0), 24)
            value = _num(fields[i + 1], 0.0) or 0.0
            i += 1
            for arr in targets:
                for h in range(cursor, hour):
                    arr[h] = value
            cursor = hour
        i += 1
    return {"weekday": weekday, "weekend": weekend}


# ---------------------------------------------------------------------------
# Main parse
# ---------------------------------------------------------------------------

def parse_idf(path: str | Path) -> IdfModel:
    objects = read_idf_objects(path)
    model = IdfModel()

    for obj in objects:
        cls, args = obj[0], obj[1:]
        if cls == "BUILDING" and args:
            model.building_name = args[0]
        elif cls == "SITE:LOCATION" and len(args) >= 4:
            model.location_name = args[0]
            model.latitude = _num(args[1], 0.0) or 0.0
            model.longitude = _num(args[2], 0.0) or 0.0
            model.timezone_offset = _num(args[3], 7.0) or 7.0
        elif cls == "ZONE" and args:
            origin = (
                _num(args[2], 0.0) or 0.0 if len(args) > 2 else 0.0,
                _num(args[3], 0.0) or 0.0 if len(args) > 3 else 0.0,
                _num(args[4], 0.0) or 0.0 if len(args) > 4 else 0.0,
            )
            model.zones[args[0]] = IdfZone(name=args[0], origin=origin)
        elif cls == "BUILDINGSURFACE:DETAILED" and len(args) >= 11:
            model.surfaces.append(IdfSurface(
                name=args[0],
                surface_type=args[1].lower(),
                construction=args[2],
                zone_name=args[3],
                boundary=args[5].lower() if len(args) > 5 else "",
                vertices=_parse_vertices(args[11:]),
            ))
        elif cls == "FENESTRATIONSURFACE:DETAILED" and len(args) >= 9:
            model.fenestrations.append(IdfFenestration(
                name=args[0],
                surface_type=args[1].lower(),
                construction=args[2],
                base_surface=args[3],
                vertices=_parse_vertices(args[9:]),
            ))
        elif cls == "CONSTRUCTION" and args:
            model.constructions[args[0]] = [a for a in args[1:] if a]
        elif cls in ("MATERIAL", "MATERIAL:NOMASS", "WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM") and args:
            model.materials[args[0]] = {"class": cls, "fields": args[1:]}
        elif cls == "SCHEDULE:COMPACT" and len(args) >= 2:
            model.schedules[args[0]] = parse_compact_schedule(args[2:])
        elif cls == "LIGHTS" and len(args) >= 6:
            zone = model.zones.get(args[1])
            if zone:
                zone.lights_schedule = args[2]
                zone.lights_w_m2 = _num(args[5], 0.0) or 0.0
        elif cls == "ELECTRICEQUIPMENT" and len(args) >= 6:
            zone = model.zones.get(args[1])
            if zone:
                zone.equip_schedule = args[2]
                zone.equip_w_m2 = _num(args[5], 0.0) or 0.0
        elif cls == "PEOPLE" and len(args) >= 6:
            zone = model.zones.get(args[1])
            if zone:
                zone.occupancy_schedule = args[2]
                zone.people_per_m2 = _num(args[5], 0.0) or 0.0
        elif cls == "HVACTEMPLATE:THERMOSTAT" and len(args) >= 4:
            model.heating_setpoint_schedule = args[1]
            model.cooling_setpoint_schedule = args[3]

    _compute_zone_geometry(model)
    return model


def _compute_zone_geometry(model: IdfModel) -> None:
    """Derive area, height, volume and centroid for each zone from its surfaces."""
    for zone in model.zones.values():
        floor_pts: list[tuple[float, float]] = []
        floor_area = 0.0
        z_min, z_max = float("inf"), float("-inf")
        all_pts: list[tuple[float, float, float]] = []
        for s in model.surfaces:
            if s.zone_name != zone.name:
                continue
            for v in s.vertices:
                all_pts.append(v)
                z_min = min(z_min, v[2])
                z_max = max(z_max, v[2])
            if s.surface_type == "floor":
                pts2d = [(v[0], v[1]) for v in s.vertices]
                floor_area += _polygon_area_2d(pts2d)
                floor_pts.extend(pts2d)
        if not all_pts:
            continue
        zone.area_m2 = round(floor_area, 2)
        zone.height_m = round(max(z_max - z_min, 0.0), 2)
        zone.volume_m3 = round(floor_area * zone.height_m, 2)
        cx = sum(p[0] for p in all_pts) / len(all_pts)
        cy = sum(p[1] for p in all_pts) / len(all_pts)
        cz = sum(p[2] for p in all_pts) / len(all_pts)
        zone.centroid = (round(cx, 3), round(cy, 3), round(cz, 3))


def zone_slug(zone_name: str) -> str:
    """'Block open_office Storey 0' -> 'storey0_open_office'."""
    m = re.match(r"Block\s+(.+?)\s+Storey\s+(\d+)", zone_name, re.IGNORECASE)
    if m:
        return f"storey{m.group(2)}_{m.group(1).strip().lower().replace(' ', '_')}"
    return re.sub(r"[^a-z0-9]+", "_", zone_name.lower()).strip("_")

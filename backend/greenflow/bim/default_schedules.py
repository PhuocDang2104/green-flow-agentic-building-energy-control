"""Default operating schedules + internal loads per room type.

IFC carries no operating schedules, so the synthetic simulation engine needs
sensible defaults. The weekday/weekend occupancy shape reuses the office
WorkHoursFrac profile from the original IDF archetype; cooling setpoints follow
the same day/night pattern. Values are typical office defaults, not measured.
"""

from __future__ import annotations

# Weekday office activity ramp (07:00 in, lunch dip, 18:00 out); weekend idle.
WORKHOURS_WEEKDAY = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.10, 0.50, 0.90, 1.0, 1.0, 1.0,
                     0.80, 0.90, 1.0, 1.0, 0.90, 0.60, 0.20, 0.10, 0.0, 0.0, 0.0, 0.0]
WORKHOURS_WEEKEND = [0.05] * 24

# Cooling setpoint: 28°C setback at night, 24°C during work hours.
COOLING_WEEKDAY = [28.0] * 7 + [24.0] * 12 + [28.0] * 5
HEATING_WEEKDAY = [18.0] * 24

SCHEDULES: dict[str, dict[str, list[float]]] = {
    "WorkHoursFrac": {"weekday": WORKHOURS_WEEKDAY, "weekend": WORKHOURS_WEEKEND},
    "CoolSetSched": {"weekday": COOLING_WEEKDAY, "weekend": [28.0] * 24},
    "HeatSetSched": {"weekday": HEATING_WEEKDAY, "weekend": [18.0] * 24},
}

# room_type -> (lights W/m2, equipment W/m2, people/m2, occupancy schedule name)
ROOM_LOADS: dict[str, tuple[float, float, float]] = {
    "open_office": (11.0, 12.0, 0.10),
    "office": (11.0, 12.0, 0.0833),
    "meeting_room": (11.0, 8.0, 0.30),
    "lobby": (9.0, 3.0, 0.05),
    "amenity": (10.0, 6.0, 0.12),
    "hallway": (5.0, 2.0, 0.025),
    "circulation": (5.0, 1.0, 0.02),
    "utility": (6.0, 4.0, 0.02),
}
DEFAULT_LOAD = (10.0, 8.0, 0.08)

COMFORT_PROFILE = {
    "open_office": "office_standard", "office": "office_standard",
    "meeting_room": "office_standard", "lobby": "relaxed",
    "amenity": "relaxed", "hallway": "relaxed", "circulation": "relaxed",
    "utility": "relaxed",
}


def loads_for(room_type: str) -> tuple[float, float, float]:
    return ROOM_LOADS.get(room_type, DEFAULT_LOAD)


def comfort_profile_for(room_type: str) -> str:
    return COMFORT_PROFILE.get(room_type, "office_standard")

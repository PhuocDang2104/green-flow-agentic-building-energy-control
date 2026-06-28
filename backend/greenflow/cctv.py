"""Deterministic demo-CCTV profiles for the 308-zone true building.

The available clips are representative, pre-annotated count-only feeds.  This
module keeps their assignment stable and semantically aligned with each space
type instead of presenting a random office clip in every zone.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class CameraProfile:
    label: str
    video_source: str


OFFICE_FEEDS = tuple(
    f"/media/cctv/open_office_{index}.webm" for index in range(1, 5)
)


def _stable_choice(entity_key: str, sources: tuple[str, ...]) -> str:
    digest = hashlib.sha256(entity_key.encode("utf-8")).digest()
    return sources[int.from_bytes(digest[:4], "big") % len(sources)]


def camera_profile(entity_key: str, zone_name: str, room_type: str) -> CameraProfile:
    """Return the representative count-only feed for a true-building zone."""
    name = zone_name.strip()
    upper_name = name.upper()

    # Known semantic rooms from the IFC metadata get the most specific feeds.
    if name == "130":
        return CameraProfile("Auditorium", "/media/cctv/auditorium_1.webm")
    if name == "140":
        return CameraProfile("Business space", "/media/cctv/business_1.webm")
    if name == "1000":
        return CameraProfile("Restaurant", "/media/cctv/restaurant_1.webm")
    if name == "110":
        return CameraProfile("Kitchen", "/media/cctv/kitchen_1.webm")
    if name == "100":
        return CameraProfile("Lobby", "/media/cctv/lobby_1.webm")
    if name == "150":
        return CameraProfile("Parking", "/media/cctv/security_1.webm")

    if room_type == "workspace":
        return CameraProfile("Workspace", _stable_choice(entity_key, OFFICE_FEEDS))
    if room_type == "meeting_event":
        return CameraProfile("Meeting room", "/media/cctv/meeting_room_1.webm")
    if room_type == "amenity":
        return CameraProfile("Amenity", "/media/cctv/lobby_1.webm")
    if room_type == "circulation":
        if "LIFT" in upper_name or name in {"201", "302", "401"}:
            return CameraProfile("Lift and stair lobby", "/media/cctv/elevator_1.webm")
        return CameraProfile("Circulation", "/media/cctv/lobby_1.webm")
    if room_type == "parking_shelter":
        return CameraProfile("Parking and shelter", "/media/cctv/security_1.webm")
    if room_type == "service":
        return CameraProfile("Service area", "/media/cctv/security_1.webm")
    if room_type == "technical_core":
        return CameraProfile("Technical area", "/media/cctv/security_1.webm")
    if room_type == "gross_area_placeholder":
        return CameraProfile("Floor overview", "/media/cctv/security_1.webm")

    # The remaining IFC helpers are turning/free-access spaces, so a
    # circulation feed is less misleading than an office or meeting clip.
    return CameraProfile("Accessible circulation", "/media/cctv/lobby_1.webm")

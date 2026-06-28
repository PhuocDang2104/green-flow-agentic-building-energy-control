"""Semantic and deterministic assignment of representative CCTV feeds."""

from greenflow.cctv import OFFICE_FEEDS, camera_profile


def test_known_rooms_receive_specific_feeds():
    assert camera_profile("zone-a", "130", "meeting_event").label == "Auditorium"
    assert camera_profile("zone-b", "1000", "amenity").label == "Restaurant"
    assert camera_profile("zone-c", "110", "amenity").label == "Kitchen"
    assert camera_profile("zone-d", "150", "parking_shelter").label == "Parking"


def test_workspace_assignment_is_stable_and_uses_office_feeds():
    first = camera_profile("zone-stable", "220", "workspace")
    second = camera_profile("zone-stable", "220", "workspace")
    assert first == second
    assert first.video_source in OFFICE_FEEDS


def test_all_true_building_room_types_receive_a_suitable_profile():
    expected = {
        "workspace": "Workspace",
        "meeting_event": "Meeting room",
        "amenity": "Amenity",
        "circulation": "Circulation",
        "parking_shelter": "Parking and shelter",
        "service": "Service area",
        "technical_core": "Technical area",
        "gross_area_placeholder": "Floor overview",
        "unknown": "Accessible circulation",
    }
    for room_type, label in expected.items():
        assert camera_profile(f"zone-{room_type}", "999", room_type).label == label


def test_lift_and_stair_zones_use_elevator_feed():
    lift = camera_profile("zone-lift", "LIFT:1423872", "circulation")
    stair = camera_profile("zone-stair", "302", "circulation")
    assert lift.video_source.endswith("elevator_1.webm")
    assert stair.video_source.endswith("elevator_1.webm")

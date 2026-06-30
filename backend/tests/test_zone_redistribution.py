from greenflow.zone_redistribution import build_child_weights, is_child_candidate


def test_build_child_weights_maps_aggregate_to_same_storey_children():
    rows = [
        {
            "zone_id": "agg_1",
            "energy_scope": "aggregate_context",
            "scope_reason": "explicit_aggregate_name",
            "floor_id": "floor_02",
            "storey": "Level_02",
            "room_type": "gross_area_placeholder",
            "long_name": "GFA",
            "area_m2": 1000,
        },
        {
            "zone_id": "child_a",
            "energy_scope": "atomic_energy_zone",
            "scope_reason": "default_atomic_space",
            "floor_id": "floor_02",
            "storey": "Level_02",
            "room_type": "office",
            "long_name": "OFFICE",
            "number": "201",
            "area_m2": 60,
        },
        {
            "zone_id": "child_b",
            "energy_scope": "atomic_energy_zone",
            "scope_reason": "default_atomic_space",
            "floor_id": "floor_02",
            "storey": "Level_02",
            "room_type": "meeting_room",
            "long_name": "MEETING",
            "number": "202",
            "area_m2": 40,
        },
        {
            "zone_id": "shaft",
            "energy_scope": "review_required",
            "scope_reason": "context_space_name",
            "floor_id": "floor_02",
            "storey": "Level_02",
            "room_type": "technical_core",
            "long_name": "SHAFT",
            "area_m2": 10,
        },
    ]

    weights, summary = build_child_weights(rows)

    assert summary.aggregate_count == 1
    assert summary.mapped_aggregate_count == 1
    assert {row["child_zone_id"] for row in weights} == {"child_a", "child_b"}
    assert round(sum(float(row["weight"]) for row in weights), 8) == 1.0
    assert {row["child_zone_id"]: row["weight"] for row in weights} == {
        "child_a": 0.6,
        "child_b": 0.4,
    }


def test_context_space_is_not_child_candidate():
    assert not is_child_candidate({
        "zone_id": "shaft",
        "energy_scope": "review_required",
        "scope_reason": "context_space_name",
        "room_type": "technical_core",
        "long_name": "SHAFT",
        "area_m2": 10,
    })


def test_building_wide_office_volume_falls_back_to_occupied_children():
    rows = [
        {
            "zone_id": "volume_office",
            "energy_scope": "aggregate_context",
            "scope_reason": "explicit_aggregate_name",
            "floor_id": "floor_foundation",
            "storey": "Foundation",
            "room_type": "workspace",
            "long_name": "VOLUME / OFFICE",
            "area_m2": 1000,
        },
        {
            "zone_id": "office_1",
            "energy_scope": "atomic_energy_zone",
            "scope_reason": "default_atomic_space",
            "floor_id": "floor_02",
            "storey": "Level_02",
            "room_type": "office",
            "long_name": "OFFICE",
            "area_m2": 75,
        },
        {
            "zone_id": "basement_1",
            "energy_scope": "atomic_energy_zone",
            "scope_reason": "default_atomic_space",
            "floor_id": "floor_basement",
            "storey": "Basement",
            "room_type": "office",
            "long_name": "OFFICE",
            "area_m2": 75,
        },
    ]

    weights, summary = build_child_weights(rows)

    assert summary.mapped_aggregate_count == 1
    assert [row["child_zone_id"] for row in weights] == ["office_1"]
    assert weights[0]["method"] == "building_wide_occupied_area_weight"

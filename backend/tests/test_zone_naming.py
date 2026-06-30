from greenflow.zone_naming import floor_label, zone_display_name, zone_space_label


def test_floor_label_normalizes_floor_and_level_tokens():
    assert floor_label("floor_02") == "Level 02"
    assert floor_label("Level_05") == "Level 05"
    assert floor_label("Foundation") == "Foundation"


def test_zone_display_name_uses_storey_room_number_and_area():
    assert zone_display_name(
        storey="Level_02",
        long_name="OFFICE",
        number="TSTO1",
        area_m2=1145.48,
        energy_scope="atomic_energy_zone",
    ) == "Level 02 · OFFICE TSTO1 · 1,145 m²"


def test_aggregate_short_numeric_name_gets_context_label():
    assert zone_display_name(
        storey="Level_04",
        room_name="1",
        room_type="gross_area_placeholder",
        area_m2=3712.13,
        energy_scope="aggregate_context",
    ) == "Level 04 · Gross area 1 · 3,712 m²"


def test_repeated_volume_label_is_collapsed():
    assert zone_space_label(
        room_name="VOLUME / OFFICE:VOLUME / OFFICE:2646424",
        energy_scope="aggregate_context",
    ) == "VOLUME / OFFICE"

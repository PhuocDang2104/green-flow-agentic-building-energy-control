from greenflow.energy_scope import (
    AGGREGATE,
    ATOMIC,
    REVIEW,
    classify_energy_scope,
    counts_toward_energy,
)


def test_volume_office_is_excluded_aggregate():
    result = classify_energy_scope(
        "VOLUME / OFFICE:VOLUME / OFFICE:2646424",
        area_m2=3712.13,
        volume_m3=30773.9,
    )
    assert result.scope == AGGREGATE
    assert result.counts_toward_energy is False
    assert result.reason == "explicit_aggregate_name"


def test_large_zone_without_aggregate_name_requires_review_but_stays_counted():
    result = classify_energy_scope("OFFICE TSTO1", area_m2=1800, height_m=3.2)
    assert result.scope == REVIEW
    assert result.counts_toward_energy is True
    assert "large_area" in result.reason


def test_regular_room_is_atomic():
    result = classify_energy_scope("MEETING ROOM 204", area_m2=42, height_m=3.1)
    assert result.scope == ATOMIC
    assert result.counts_toward_energy is True


def test_csv_boolean_parser_handles_false_string():
    assert counts_toward_energy("False") is False
    assert counts_toward_energy("true") is True

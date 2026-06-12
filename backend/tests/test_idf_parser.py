"""IDF parser tests against the real archetype file (REPO_BUILD_SPEC §17.1)."""


def test_zones_parsed(idf_model):
    assert len(idf_model.zones) == 5
    names = set(idf_model.zones)
    assert "Block open_office Storey 0" in names


def test_geometry_counts(idf_model):
    assert len(idf_model.surfaces) == 30
    assert len(idf_model.fenestrations) == 20


def test_zone_geometry_derived(idf_model):
    z = idf_model.zones["Block open_office Storey 0"]
    assert 150 < z.area_m2 < 250
    assert z.height_m == 3.5
    assert z.volume_m3 > 0


def test_internal_loads_parsed(idf_model):
    z = idf_model.zones["Block open_office Storey 0"]
    assert z.lights_w_m2 == 11.0
    assert z.equip_w_m2 == 12.0
    assert z.people_per_m2 == 0.1
    assert z.occupancy_schedule == "Occ_open_office"


def test_schedule_compact_weekday_weekend(idf_model):
    sched = idf_model.schedules["WorkHoursFrac"]
    assert sched["weekday"][10] == 1.0      # mid-morning full
    assert sched["weekday"][2] == 0.0       # night off
    assert sched["weekend"][10] == 0.05     # weekend trickle


def test_cooling_setpoint_schedule(idf_model):
    cool = idf_model.schedules[idf_model.cooling_setpoint_schedule]["weekday"]
    assert cool[10] == 24.0
    assert cool[2] == 28.0


def test_normalized_devices_and_relations(normalized):
    assert len(normalized["zones"]) == 5
    # 3 devices per zone + AHU + board
    assert len(normalized["devices"]) == 17
    controllable = [d for d in normalized["devices"] if d["controllable"]]
    assert len(controllable) == 11
    rels = normalized["entity_relations"]
    assert any(r["relation"] == "SUPPLIES_AIR_TO" for r in rels)
    assert any(r["relation"] == "HAS_FLOOR" for r in rels)


def test_zone_equipment_map(normalized):
    zmap = normalized["zone_equipment_map"]
    assert len(zmap) == 5
    for devices in zmap.values():
        assert len(devices) == 3

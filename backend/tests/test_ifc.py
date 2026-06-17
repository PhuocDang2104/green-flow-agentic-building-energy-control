"""IFC extraction helpers + (optional) end-to-end extract on the enriched files.

The heavy enriched IFC files are git-ignored; the end-to-end test skips when
they are absent or when ifcopenshell is not installed.
"""

from pathlib import Path

import pytest

from greenflow.bim import default_schedules as ds

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "data" / "enriched_IFC" / "ARCH_AsBuilt_enriched.ifc"


def test_default_loads_known_room_types():
    for rt in ("open_office", "office", "meeting_room", "hallway", "amenity"):
        lights, equip, ppl = ds.loads_for(rt)
        assert lights > 0 and equip >= 0 and 0 <= ppl <= 1


def test_default_loads_fallback():
    assert ds.loads_for("unknown_type") == ds.DEFAULT_LOAD


def test_schedule_shapes():
    wk = ds.SCHEDULES["WorkHoursFrac"]["weekday"]
    assert len(wk) == 24 and wk[10] == 1.0 and wk[2] == 0.0
    cool = ds.SCHEDULES["CoolSetSched"]["weekday"]
    assert cool[10] == 24.0 and cool[2] == 28.0


def test_norm_room_type():
    from greenflow.bim.ifc_geometry import _norm_room_type
    assert _norm_room_type("OPEN OFFICE") == "open_office"
    assert _norm_room_type("Meeting Room") == "meeting_room"
    assert _norm_room_type("CORRIDOR") == "hallway"
    assert _norm_room_type("STAIRCASE") == "circulation"
    assert _norm_room_type("Lobby") == "lobby"


def test_guid_to_id_preserves_case():
    from greenflow.bim.ifc_geometry import guid_to_id
    a = guid_to_id("3xtnrBUgHBCwRh$xfyB626")
    b = guid_to_id("3xtnrBUgHBCwRh$xfyB6Z6")
    assert a != b               # case/char preserved -> no collision
    assert a.startswith("zone_") and "$" not in a


@pytest.mark.skipif(not ARCH.exists(), reason="enriched IFC not present")
def test_extract_ifc_end_to_end():
    pytest.importorskip("ifcopenshell")
    from greenflow.bim.ifc_extractor import extract_ifc
    from greenflow.sim.synthetic_baseline import (run_synthetic,
                                                  zone_specs_from_normalized)
    n = extract_ifc(ARCH)
    assert n["building"]["space_count"] == 308
    assert 8 <= n["building"]["zone_count"] <= 16
    assert n["devices"] and n["schedules"]
    # zones must drive the synthetic engine
    result = run_synthetic(zone_specs_from_normalized(n))
    assert result.totals["energy_kwh"] > 0

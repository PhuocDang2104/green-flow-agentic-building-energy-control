"""Surrogate forecast + scoring tests (no DB; model files shipped in ml/models/)."""
from datetime import datetime

import pytest

from greenflow.ml.forecast_service import ForecastService, archetype_of

svc = ForecastService.load_default()
pytestmark = pytest.mark.skipif(svc is None, reason="surrogate model/lightgbm not available")

NOON = datetime(2025, 7, 15, 14, 0)


def test_room_type_maps_to_archetype():
    assert archetype_of("meeting_room") == "meeting"
    assert archetype_of("hallway") == "circulation"
    assert archetype_of("open_office") == "open_office"


def test_eco_mode_saves_energy():
    wi = svc.what_if("open_office", 190.0, NOON, 120, 24.0, +1.5)
    saving = (wi.baseline_elec_kwh - wi.action_elec_kwh).sum()
    assert saving > 0           # raising setpoint cuts cooling electricity
    assert 0 < wi.confidence <= 1


def test_setpoint_elasticity_direction():
    # cooling giảm khi setpoint tăng (so cùng điều kiện)
    idx = [NOON]
    low, _ = svc.predict("open_office", 190.0, idx, 23.0)
    high, _ = svc.predict("open_office", 190.0, idx, 27.0)
    assert high[0] < low[0]


def test_pre_cooling_costs_energy_upfront():
    # pre-cool = hạ setpoint -> dùng NHIỀU điện hơn trong cửa sổ (saving âm) — đúng bản chất
    wi = svc.what_if("open_office", 190.0, NOON, 120, 24.0, -1.0)
    saving = (wi.baseline_elec_kwh - wi.action_elec_kwh).sum()
    assert saving < 0


def test_scoring_returns_regret_compatible_keys():
    from greenflow.ml.scoring import score_zone_action
    k = score_zone_action(svc, "hvac_eco_mode", "open_office", 190.0, 13.0, 15.0)
    for key in ("saving_kwh", "cost_saving_vnd", "peak_reduction_kw",
                "comfort_violation_delta_min", "rebound_kwh"):
        assert key in k
    assert k["saving_kwh"] > 0

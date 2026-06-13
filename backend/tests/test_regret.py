"""Regrettable-substitution check tests (spine D8)."""

from greenflow.agent.policy import evaluate_action
from greenflow.agent.regret import regrettable_substitution_check

GOOD_KPI = {
    "saving_kwh": 12.0,
    "cost_saving_vnd": 30000,
    "peak_reduction_kw": 2.0,
    "comfort_violation_delta_min": 0.0,
}

GOOD_CONTEXT = {
    "zone_types": {"zone_a": "open_office"},
    "occupancy_confidence": 0.9,
    "forecast_confidence": 0.85,
    "comfort_risk_after": 0.1,
    "peak_risk_after": 0.2,
    "zones_affected": 1,
    "kpi": GOOD_KPI,
}


def _action(action_type="lighting_reduction"):
    return {"action_type": action_type, "target_zone_keys": ["zone_a"],
            "setpoint_delta_c": None}


def test_clean_kpi_passes_and_auto_runs():
    result = evaluate_action(_action(), GOOD_CONTEXT)
    assert result["decision"] == "auto_run"
    assert result["regrettable_check"]["passed"]


def test_comfort_tradeoff_flagged_and_escalates():
    kpi = {**GOOD_KPI, "comfort_violation_delta_min": 45.0}
    result = evaluate_action(_action(), {**GOOD_CONTEXT, "kpi": kpi})
    assert result["decision"] == "approval_required"
    assert "regrettable_substitution" in result["violated_rules"]
    assert result["regrettable_check"]["flags"][0]["dimension"] == "comfort"


def test_new_peak_flagged():
    kpi = {**GOOD_KPI, "peak_reduction_kw": -8.0}
    check = regrettable_substitution_check(kpi)
    assert not check["passed"]
    assert check["flags"][0]["dimension"] == "peak"


def test_cost_inversion_flagged():
    kpi = {**GOOD_KPI, "cost_saving_vnd": -5000}
    check = regrettable_substitution_check(kpi)
    assert not check["passed"]
    assert check["flags"][0]["dimension"] == "cost"


def test_rebound_flagged_when_reported():
    kpi = {**GOOD_KPI, "rebound_kwh": 9.0}  # > 50% of 12 kWh saving
    check = regrettable_substitution_check(kpi)
    assert not check["passed"]
    assert check["flags"][0]["dimension"] == "rebound"


def test_rebound_skipped_when_engine_does_not_report_it():
    check = regrettable_substitution_check(GOOD_KPI)  # no rebound_kwh key
    assert check["passed"]


def test_missing_kpi_is_no_evidence_not_a_block():
    result = evaluate_action(_action(), {**GOOD_CONTEXT, "kpi": {}})
    assert result["decision"] == "auto_run"


def test_thresholds_overridable():
    kpi = {**GOOD_KPI, "comfort_violation_delta_min": 10.0}
    strict = regrettable_substitution_check(kpi, {"max_comfort_delta_min": 5.0})
    assert not strict["passed"]

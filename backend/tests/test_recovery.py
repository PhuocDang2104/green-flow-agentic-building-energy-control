"""Controlled-loop recovery tests: retry/fallback, budgets, degraded->approval,
self-describing tool errors (slide §Orchestration + §Tools).

The fallback/policy/budget tests are pure-logic (no DB). The plan_executor and
data_tools tests import modules that pull optional deps (fpdf via the report
node); they import inside the test and skip cleanly when those are absent, and
run for real in the container where the deps exist.
"""

import pytest

from greenflow.agent.policy import evaluate_action
from greenflow.agent.recovery import fallback_prediction, fallback_simulation
from greenflow.agent.state import new_state

# --------------------------------------------------------------------------- #
# Fallbacks (deterministic, clearly degraded, low confidence)                 #
# --------------------------------------------------------------------------- #


def test_fallback_prediction_is_persistence_with_low_confidence():
    state = new_state(building_id="b",
                      zones=[{"entity_key": "z1", "name": "Z1"}],
                      latest_zone_state={"z1": {"total_power_kw": 10.0,
                                                "comfort_risk": "high"}})
    out = fallback_prediction(state, RuntimeError("boom"))
    fr = out["forecast_result"]
    assert fr["building_load_now_kw"] == 10.0
    assert fr["building_load_forecast_kw"] == 10.0          # persistence: held flat
    assert "z1" in fr["high_comfort_risk_zones"]            # comfort_risk high -> 0.7
    assert out["forecast_confidence"] == 0.3               # below policy threshold
    assert out["prediction_explanation"]["model"] == "fallback_persistence_v0"


def test_fallback_simulation_aggregates_quick_estimates_and_marks_degraded():
    state = new_state(building_id="b", selected_actions=[
        {"action_type": "lighting_reduction", "expected_saving_kwh": 2.0,
         "expected_peak_reduction_kw": 0.5},
        {"action_type": "hvac_eco_mode", "expected_saving_kwh": 1.0},
    ])
    sim = fallback_simulation(state, RuntimeError("x"))["simulation_result"]
    assert sim["engine"] == "fallback_quick_estimate"
    assert sim["expected_saving_kwh"] == 3.0
    assert sim["expected_peak_reduction_kw"] == 0.5
    assert sim["degraded"] is True


# --------------------------------------------------------------------------- #
# Degraded inputs must never auto-run                                         #
# --------------------------------------------------------------------------- #

_AUTO_OK = {
    "zone_types": {"zone_a": "open_office"},
    "occupancy_confidence": 0.9,
    "forecast_confidence": 0.85,
    "comfort_risk_after": 0.1,
    "peak_risk_after": 0.2,
    "zones_affected": 1,
}


def _auto_action():
    return {"action_type": "lighting_reduction", "target_zone_keys": ["zone_a"],
            "setpoint_delta_c": None}


def test_degraded_inputs_force_approval():
    ok = evaluate_action(_auto_action(), _AUTO_OK)
    assert ok["decision"] == "auto_run"
    degraded = evaluate_action(_auto_action(), {**_AUTO_OK, "degraded": True})
    assert degraded["decision"] == "approval_required"
    assert "degraded_result" in degraded["violated_rules"]


# --------------------------------------------------------------------------- #
# Budget defaults + stop_reason                                               #
# --------------------------------------------------------------------------- #


def test_new_state_budget_defaults():
    s = new_state(building_id="b")
    assert s["max_steps"] == 12
    assert s["timeout_ms"] == 120000
    assert s["stop_reason"] is None
    assert s["degraded_nodes"] == []


def _graph_or_skip():
    try:
        from greenflow.agent import graph
        return graph
    except Exception as exc:  # noqa: BLE001 — optional deps (fpdf) absent locally
        pytest.skip(f"graph import needs optional deps: {exc}")


def test_plan_executor_max_steps_budget():
    graph = _graph_or_skip()
    st = new_state(building_id="b", max_steps=0,
                   orchestration_plan=[{"step": 1, "node": "building_semantic",
                                        "status": "pending"}])
    out = graph.plan_executor(st)
    assert out["stop_reason"] == "max_steps"
    assert out["current_plan_step"] == 0           # budget tripped before any node ran


def test_plan_executor_timeout_budget():
    graph = _graph_or_skip()
    st = new_state(building_id="b", timeout_ms=-1,
                   orchestration_plan=[{"step": 1, "node": "building_semantic",
                                        "status": "pending"}])
    out = graph.plan_executor(st)
    assert out["stop_reason"] == "timeout"
    assert out["current_plan_step"] == 0


# --------------------------------------------------------------------------- #
# Self-describing tool errors                                                 #
# --------------------------------------------------------------------------- #


def _zone_timeseries_or_skip():
    try:
        from greenflow.chat.data_tools import get_zone_timeseries
        return get_zone_timeseries
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"data_tools import needs optional deps: {exc}")


def test_tool_error_lists_available_and_suggests():
    get_zone_timeseries = _zone_timeseries_or_skip()
    # metric is validated before any DB access -> conn=None is fine
    res = get_zone_timeseries(None, "b", "z1", metric="total_power")
    assert "error" in res
    assert "total_power_kw" in res["available"]
    assert res.get("hint") == "did you mean 'total_power_kw'?"

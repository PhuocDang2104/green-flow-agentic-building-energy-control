"""Policy Engine guardrail tests (REPO_BUILD_SPEC §17.3)."""

from greenflow.agent.policy import evaluate_action

GOOD_CONTEXT = {
    "zone_types": {"zone_a": "open_office", "zone_server": "server_room"},
    "occupancy_confidence": 0.9,
    "forecast_confidence": 0.85,
    "comfort_risk_after": 0.1,
    "peak_risk_after": 0.2,
    "zones_affected": 1,
}


def _action(action_type="lighting_reduction", zones=None, delta=None):
    return {"action_type": action_type,
            "target_zone_keys": zones or ["zone_a"],
            "setpoint_delta_c": delta}


def test_low_risk_lighting_reduction_auto_runs():
    result = evaluate_action(_action(), GOOD_CONTEXT)
    assert result["decision"] == "auto_run"


def test_server_room_action_rejected():
    result = evaluate_action(_action(zones=["zone_server"]), GOOD_CONTEXT)
    assert result["decision"] == "rejected"
    assert "blocked_zone_types" in result["violated_rules"]


def test_low_occupancy_confidence_blocks_auto():
    ctx = {**GOOD_CONTEXT, "occupancy_confidence": 0.5}
    result = evaluate_action(_action(), ctx)
    assert result["decision"] == "approval_required"
    assert "min_occupancy_confidence" in result["violated_rules"]


def test_comfort_risk_after_blocks_auto():
    ctx = {**GOOD_CONTEXT, "comfort_risk_after": 0.5}
    result = evaluate_action(_action(), ctx)
    assert result["decision"] == "approval_required"
    assert "max_comfort_risk_after" in result["violated_rules"]


def test_pre_cooling_requires_approval():
    result = evaluate_action(_action("pre_cooling"), GOOD_CONTEXT)
    assert result["decision"] == "approval_required"


def test_excessive_setpoint_delta_rejected():
    result = evaluate_action(_action("hvac_eco_mode", delta=3.0), GOOD_CONTEXT)
    assert result["decision"] == "rejected"


def test_whole_building_shutdown_rejected():
    result = evaluate_action(_action("whole_building_hvac_shutdown"), GOOD_CONTEXT)
    assert result["decision"] == "rejected"


def test_too_many_zones_escalates():
    ctx = {**GOOD_CONTEXT, "zones_affected": 5}
    result = evaluate_action(_action(), ctx)
    assert result["decision"] == "approval_required"

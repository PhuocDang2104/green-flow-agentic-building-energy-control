"""QC regression invariants (GF-QC-01 / QC-02 / QC-03).

Encodes the cross-page invariants the QC team asked for after the fixes:
  - the selected forecast horizon must reach the agent (not stay at 60),
  - the per-run "Allow auto-actions" switch must actually gate the policy,
  - the same metric ("today" energy) must read identically on Copilot and the
    dashboard, and the pending-approval count must match the Action Queue.

The pure-logic invariants run without a database (like the rest of the suite).
The two cross-page data-consistency checks need a live DB + telemetry and skip
cleanly when one is not reachable.
"""

import pytest

from greenflow.agent.policy import evaluate_action
from greenflow.agent.state import new_state

# --------------------------------------------------------------------------- #
# QC-02: the UI scenario_config must actually reach the agent                  #
# --------------------------------------------------------------------------- #


def test_horizon_minutes_wired_from_scenario():
    state = new_state(entrypoint="button", button_action="run_optimization",
                      building_id="b",
                      scenario_config={"horizon_minutes": 15, "allow_auto_action": True})
    assert state["forecast_horizon_minutes"] == 15  # not the 60 default (QC-02)


def test_horizon_defaults_to_60_without_scenario():
    state = new_state(entrypoint="chatbot", building_id="b")
    assert state["forecast_horizon_minutes"] == 60


def test_allow_auto_action_defaults_true():
    state = new_state(entrypoint="button", button_action="run_optimization", building_id="b")
    assert state["allow_auto_action"] is True


def test_allow_auto_action_false_is_carried():
    state = new_state(entrypoint="button", button_action="run_optimization", building_id="b",
                      scenario_config={"allow_auto_action": False})
    assert state["allow_auto_action"] is False


_AUTO_OK_CONTEXT = {
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


def test_allow_auto_action_false_forces_approval():
    """Unticking "Allow auto-actions" must escalate an otherwise-auto action to
    human approval (QC-02 + Human-in-the-Loop guardrail)."""
    auto = evaluate_action(_auto_action(), {**_AUTO_OK_CONTEXT, "allow_auto_action": True})
    assert auto["decision"] == "auto_run"
    blocked = evaluate_action(_auto_action(), {**_AUTO_OK_CONTEXT, "allow_auto_action": False})
    assert blocked["decision"] == "approval_required"
    assert "auto_disabled" in blocked["violated_rules"]


# --------------------------------------------------------------------------- #
# QC-01 / QC-03: cross-page data consistency (requires a database)             #
# --------------------------------------------------------------------------- #


@pytest.fixture
def db_building():
    """Default building_id if a DB with telemetry is reachable, else skip."""
    try:
        from greenflow.api.deps import default_building_id
        from greenflow.db import db_conn
        from greenflow.replayclock import anchor
        b = default_building_id()
        with db_conn() as conn:
            if anchor(conn, b) is None:
                pytest.skip("no telemetry in DB")
        return b
    except Exception as exc:  # noqa: BLE001 — DB not configured in this env
        pytest.skip(f"no database available: {exc}")


def test_today_energy_matches_between_copilot_and_dashboard(db_building):
    """QC-01: 'today' energy must be identical on Copilot and the dashboard."""
    from greenflow.agent.tools.timeseries_tool import get_building_kpis
    from greenflow.chat.data_tools import get_building_kpi
    from greenflow.db import db_conn

    dashboard = get_building_kpis(db_building)
    with db_conn() as conn:
        copilot = get_building_kpi(conn, db_building, window="day")
    assert round(float(copilot["energy_kwh"])) == round(float(dashboard["kwh"]))


def test_pending_count_matches_queue(db_building):
    """QC-03: dashboard pending KPI == number of pending_approval actions the
    Action Queue would show (count summary == count detail)."""
    from greenflow.agent.tools.timeseries_tool import get_building_kpis
    from greenflow.db import db_conn, fetch_one

    dashboard = get_building_kpis(db_building)
    with db_conn() as conn:
        row = fetch_one(conn, """
            SELECT count(*) AS n FROM actions
            WHERE building_id = :b AND status = 'pending_approval'
        """, b=db_building)
    assert int(dashboard["pending"]) == int(row["n"])

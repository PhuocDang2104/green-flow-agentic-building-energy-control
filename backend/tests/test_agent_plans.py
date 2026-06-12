"""Orchestration planner + intent classifier tests (REPO_BUILD_SPEC §17.4).

These run without a database or LLM (LLM_PROVIDER=none default).
"""

from greenflow.agent.nodes.intent import _classify_keywords
from greenflow.agent.nodes.planner import run as plan
from greenflow.agent.state import new_state


def _plan_steps(state):
    return [s["node"] for s in plan(state)["orchestration_plan"]]


def test_run_optimization_button_plan():
    state = new_state(entrypoint="button", button_action="run_optimization",
                      building_id="b")
    steps = _plan_steps(state)
    assert steps == ["building_semantic", "prediction", "control", "simulation",
                     "policy", "execution"]


def test_report_button_plan():
    state = new_state(entrypoint="button", button_action="building_semantic_report",
                      building_id="b")
    assert _plan_steps(state) == ["building_semantic", "report"]


def test_compare_button_plan():
    state = new_state(entrypoint="button", button_action="compare_baseline_optimized",
                      building_id="b")
    assert _plan_steps(state) == ["building_semantic", "compare"]


def test_chat_what_if_intent_creates_simulation_plan():
    intent = _classify_keywords("nếu tăng setpoint 1 độ thì sao")
    assert intent == "what_if_simulation_query"
    state = new_state(entrypoint="chatbot", intent=intent, building_id="b")
    assert "simulation" in _plan_steps(state)


def test_chat_intents_keyword_rules():
    assert _classify_keywords("zone nào đang lãng phí điện") in (
        "energy_query", "occupancy_query")
    assert _classify_keywords("tối ưu vận hành tòa nhà") == "optimization_request"
    assert _classify_keywords("báo cáo hvac") == "report_request"
    assert _classify_keywords("peak demand hôm nay") == "peak_strategy_query"
    assert _classify_keywords("so sánh baseline") == "baseline_comparison_query"
    assert _classify_keywords("hello") == "general_help"


def test_default_plan_is_semantic():
    state = new_state(entrypoint="chatbot", intent="general_help", building_id="b")
    assert _plan_steps(state) == ["building_semantic"]

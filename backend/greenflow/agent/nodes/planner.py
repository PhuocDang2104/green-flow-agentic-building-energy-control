"""Orchestration Planner: intent -> ordered list of executable steps.

Buttons use fixed workflow templates (blueprint §7.1); chatbot intents get
dynamic plans assembled from the same step vocabulary.
"""

from __future__ import annotations

from ..state import GreenFlowState

# Step vocabulary maps 1:1 to node functions registered in graph.py
BUTTON_PLANS: dict[str, list[str]] = {
    "run_optimization": [
        "building_semantic", "prediction", "control", "simulation",
        "policy", "execution",
    ],
    "building_semantic_report": ["building_semantic", "report"],
    "hvac_elec_report": ["building_semantic", "report"],
    "peak_strategy": [
        "building_semantic", "prediction", "control", "simulation", "policy",
        "execution",
    ],
    "compare_baseline_optimized": ["building_semantic", "compare"],
    "run_prediction": ["building_semantic", "prediction"],
}

INTENT_PLANS: dict[str, list[str]] = {
    "semantic_query": ["building_semantic"],
    "hvac_elec_query": ["building_semantic"],
    "energy_query": ["building_semantic", "prediction"],
    "comfort_query": ["building_semantic", "prediction"],
    "occupancy_query": ["building_semantic"],
    "what_if_simulation_query": ["building_semantic", "prediction", "control",
                                 "simulation"],
    "optimization_request": BUTTON_PLANS["run_optimization"],
    "peak_strategy_query": BUTTON_PLANS["peak_strategy"],
    "baseline_comparison_query": ["building_semantic", "compare"],
    "report_request": ["building_semantic", "report"],
    "explain_action_query": ["building_semantic"],
    "general_help": ["building_semantic"],
}


def run(state: GreenFlowState) -> dict:
    if state.get("entrypoint") == "button":
        steps = BUTTON_PLANS.get(state.get("button_action") or "", ["building_semantic"])
    else:
        steps = INTENT_PLANS.get(state.get("intent") or "general_help",
                                 ["building_semantic"])
    plan = [{"step": i + 1, "node": node, "status": "pending"}
            for i, node in enumerate(steps)]
    return {"orchestration_plan": plan, "current_plan_step": 0}

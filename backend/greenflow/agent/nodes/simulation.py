"""Simulation Agent: verify selected actions with counterfactual runs.

Runs baseline vs actions on identical inputs and attaches per-action KPI.
"""

from __future__ import annotations

from ...sim.actions import Action
from ..state import GreenFlowState
from ..tools import simulation_tool


def run(state: GreenFlowState) -> dict:
    selected = state.get("selected_actions", [])
    if not selected:
        return {"simulation_result": {"note": "no actions to simulate"}}

    actions = [Action.from_dict(a) for a in selected]

    # Combined plan simulation (what gets persisted and compared)
    combined = simulation_tool.simulate_actions(
        state["building_id"], actions, persist=True, run_kind="agent")

    # Per-action attribution (lighter, not persisted)
    per_action = []
    for a in actions:
        solo = simulation_tool.simulate_actions(
            state["building_id"], [a], persist=False)
        kpi = solo["kpi"]
        per_action.append({
            "action_type": a.action_type,
            "target_zone_keys": a.target_zone_keys,
            "saving_kwh": kpi["saving_kwh"],
            "cost_saving_vnd": kpi["cost_saving_vnd"],
            "peak_reduction_kw": kpi["peak_reduction_kw"],
            "comfort_violation_delta_min": kpi["comfort_violation_delta_min"],
        })

    kpi = combined["kpi"]
    comfort_after = min(1.0, max(0.0, kpi["comfort_violation_optimized_min"] / 480.0))
    simulation_result = {
        "engine": combined["engine"],
        "expected_saving_kwh": kpi["saving_kwh"],
        "expected_cost_saving_vnd": kpi["cost_saving_vnd"],
        "expected_peak_reduction_kw": kpi["peak_reduction_kw"],
        "comfort_violation_delta_min": kpi["comfort_violation_delta_min"],
        "comfort_risk_after": round(comfort_after, 2),
        "baseline_run_id": combined.get("baseline_run_id"),
        "optimized_run_id": combined.get("optimized_run_id"),
        "per_action": per_action,
    }

    # Enrich selected actions with their simulated impact
    enriched = []
    for a_dict in selected:
        match = next((p for p in per_action
                      if p["action_type"] == a_dict["action_type"]
                      and p["target_zone_keys"] == a_dict["target_zone_keys"]), None)
        merged = dict(a_dict)
        if match:
            merged["expected_saving_kwh"] = match["saving_kwh"]
            merged["expected_cost_saving_vnd"] = match["cost_saving_vnd"]
            merged["expected_peak_reduction_kw"] = match["peak_reduction_kw"]
            merged["comfort_violation_delta_min"] = match["comfort_violation_delta_min"]
        enriched.append(merged)

    return {
        "simulation_result": simulation_result,
        "baseline_vs_optimized": kpi,
        "selected_actions": enriched,
    }

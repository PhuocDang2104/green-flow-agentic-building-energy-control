"""Policy Engine node: classify each selected action auto/approval/reject."""

from __future__ import annotations

from ..policy import evaluate_action
from ..state import GreenFlowState
from .prediction import CAPACITY_KW, peak_risk_from_utilization


def run(state: GreenFlowState) -> dict:
    zone_types = state.get("semantic_context", {}).get("zone_types", {})
    sim = state.get("simulation_result", {})
    zone_state = state.get("latest_zone_state", {})

    occ_confs = [s.get("occupancy_confidence") for s in zone_state.values()
                 if s.get("occupancy_confidence") is not None]
    occupancy_confidence = min(occ_confs) if occ_confs else 0.8

    # Peak risk after = simulated optimized peak-window demand vs contracted
    # demand (same ramp as the Prediction Agent), falling back to forecast risk.
    kpi = state.get("baseline_vs_optimized", {})
    if kpi.get("peak_window_optimized_kw") is not None:
        peak_risk_after = peak_risk_from_utilization(
            kpi["peak_window_optimized_kw"] / CAPACITY_KW)
    else:
        peak_risk_after = state.get("peak_risk", {}).get("value", 0.0)

    decisions = []
    approval_needed = False
    for action in state.get("selected_actions", []):
        context = {
            "zone_types": zone_types,
            "occupancy_confidence": occupancy_confidence,
            "forecast_confidence": state.get("forecast_confidence", 0.8),
            "comfort_risk_after": sim.get("comfort_risk_after", 0.0),
            "peak_risk_after": peak_risk_after,
            "zones_affected": len(action.get("target_zone_keys", []))
                              or len(state.get("zones", [])),
            "kpi": kpi,  # regrettable-substitution check (agent/regret.py)
        }
        decision = evaluate_action(action, context)
        decisions.append({"action": action, **decision})
        if decision["decision"] == "approval_required":
            approval_needed = True

    return {
        "policy_decisions": decisions,
        "approval_required": approval_needed,
        "final_action_plan": [
            {**d["action"], "policy_decision": d["decision"],
             "risk_level": d["risk_level"], "policy_reasons": d["reasons"]}
            for d in decisions
        ],
    }

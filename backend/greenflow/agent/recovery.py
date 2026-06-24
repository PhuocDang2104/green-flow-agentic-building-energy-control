"""Controlled-loop recovery: per-node retry policy + deterministic fallbacks.

The plan executor is GreenFlow's orchestration layer (slide §4 Orchestration):
it must keep a run safe and finishable even when a node fails. Strategy, in
order:

  1. retry transient failures a small number of times — but ONLY for read-only
     nodes; side-effecting nodes (simulation persists a run, execution writes
     actions) are never retried, to avoid double-writes;
  2. else fall back to a deterministic, clearly *degraded* result — never a
     fabricated confident number — and lower confidence so the policy gate
     escalates the actions to human approval;
  3. else, for a critical node, stop the run with stop_reason="insufficient_data"
     instead of producing garbage downstream.
"""

from __future__ import annotations

from .state import GreenFlowState

# Attempts per node (1 = no retry). Read-only nodes may retry to ride out a
# transient DB hiccup. simulation/execution are side-effecting -> never retried.
NODE_RETRIES: dict[str, int] = {
    "building_semantic": 2,
    "prediction": 2,
    "compare": 2,
}
DEFAULT_RETRIES = 1

# Nodes whose hard failure makes the rest of the plan meaningless.
CRITICAL_NODES = {"building_semantic"}

# Rough tariff for degraded cost estimates (≈ observed VND/kWh on the demo data).
_VND_PER_KWH = 2300


def fallback_prediction(state: GreenFlowState, exc: Exception) -> dict:
    """Persistence forecast: hold the current load as the forecast and derive
    comfort risk from the latest labels. Confidence is set low (below the policy
    threshold) so any downstream action requires human approval."""
    zones = state.get("zones", [])
    zone_state = state.get("latest_zone_state", {})
    zone_load: dict[str, dict] = {}
    comfort_risk: dict[str, float] = {}
    high: list[str] = []
    total_now = 0.0
    for z in zones:
        st = zone_state.get(z["entity_key"])
        if not st:
            continue
        load = st.get("total_power_kw") or 0.0
        total_now += load
        zone_load[z["entity_key"]] = {"now_kw": load, "forecast_kw": load,
                                      "schedule_ratio": 1.0}
        label = st.get("comfort_risk")
        risk = 0.7 if label == "high" else 0.4 if label == "watch" else 0.0
        comfort_risk[z["entity_key"]] = risk
        if risk >= 0.5:
            high.append(z["entity_key"])
    return {
        "forecast_result": {
            "zone_load_forecast": zone_load,
            "zone_temperature_forecast": {},
            "building_load_now_kw": round(total_now, 2),
            "building_load_forecast_kw": round(total_now, 2),  # persistence
            "high_comfort_risk_zones": high,
        },
        "comfort_risk": comfort_risk,
        "peak_risk": {"value": 0.0, "level": "normal", "in_peak_window": False},
        "demand_forecast": {},
        "forecast_confidence": 0.3,  # < policy min_forecast_confidence -> approval
        "prediction_explanation": {
            "model": "fallback_persistence_v0",
            "notes": f"Prediction Agent failed ({exc}); held current load as a "
                     "persistence forecast. Confidence lowered; actions will "
                     "require human approval.",
        },
    }


def fallback_simulation(state: GreenFlowState, exc: Exception) -> dict:
    """Quick-estimate fallback: aggregate the Level-1 estimates the Control Agent
    already attached to each selected action (no counterfactual run, no persist).
    Marked degraded so the policy gate forces approval."""
    selected = state.get("selected_actions", [])
    saving = round(sum(a.get("expected_saving_kwh") or 0.0 for a in selected), 2)
    peak = round(sum(a.get("expected_peak_reduction_kw") or 0.0 for a in selected), 2)
    return {
        "simulation_result": {
            "engine": "fallback_quick_estimate",
            "expected_saving_kwh": saving,
            "expected_cost_saving_vnd": round(saving * _VND_PER_KWH),
            "expected_peak_reduction_kw": peak,
            "comfort_violation_delta_min": 0,
            "comfort_risk_after": 0.0,
            "degraded": True,
            "note": f"Simulation Agent failed ({exc}); used quick-estimate values "
                    "instead of a counterfactual run. Low confidence; actions "
                    "require human approval.",
        },
        "baseline_vs_optimized": {},
    }


FALLBACKS = {
    "prediction": fallback_prediction,
    "simulation": fallback_simulation,
}

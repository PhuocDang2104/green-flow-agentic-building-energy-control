"""Control Agent: rule-based candidate action generation + ranking.

Turns abnormal findings + forecast into concrete candidate actions with
explicit targets. The LLM (if configured) only polishes the human-readable
reason text — action selection itself stays deterministic and auditable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ...sim.actions import make_action
from ..llm import llm_text
from ..state import GreenFlowState
from ..tools.simulation_tool import quick_estimate

TZ = timezone(timedelta(hours=7))


def run(state: GreenFlowState) -> dict:
    findings = state.get("abnormal_findings", [])
    comfort_risk = state.get("comfort_risk", {})
    peak_risk = state.get("peak_risk", {})
    zones = state.get("zones", [])
    now_hour = datetime.now(TZ).hour
    peak_mode = bool(state.get("scenario_config", {}).get("peak_strategy"))

    candidates = []

    for f in findings:
        if f["finding_type"] == "lighting_on_empty_zone":
            candidates.append(make_action(
                "turn_off_non_critical_lighting", [f["zone_key"]],
                start_hour=now_hour, end_hour=min(now_hour + 3, 24),
                reason=f"{f['zone_name']} is empty with lighting still on"))
        elif f["finding_type"] == "hvac_on_empty_zone":
            candidates.append(make_action(
                "hvac_eco_mode", [f["zone_key"]],
                start_hour=now_hour, end_hour=min(now_hour + 2, 24),
                reason=f"HVAC running in empty {f['zone_name']}"))
        elif f["finding_type"] == "comfort_risk_high":
            candidates.append(make_action(
                "alert_or_ticket", [f["zone_key"]],
                reason=f"Comfort violation in {f['zone_name']}: notify facilities"))

    # Low-comfort-risk zones can absorb a light setback during expensive hours
    low_risk_zones = [k for k, v in comfort_risk.items() if v < 0.15]
    if low_risk_zones and 8 <= now_hour < 18:
        candidates.append(make_action(
            "hvac_setback_light", low_risk_zones[:3],
            start_hour=now_hour, end_hour=min(now_hour + 3, 24),
            reason="Low comfort risk allows +0.5C setback in selected zones"))

    if peak_risk.get("level") in ("watch", "high") or peak_mode:
        candidates.append(make_action(
            "pre_cooling", [], start_hour=11, end_hour=13,
            reason="Charge thermal mass before the 13:00-16:00 peak window"))
        candidates.append(make_action(
            "peak_load_reduction", [], start_hour=13, end_hour=16,
            reason="Raise setpoints and dim lighting through the peak window"))
        big_zones = sorted(zones, key=lambda z: -(z.get("area_m2") or 0))[:2]
        candidates.append(make_action(
            "lighting_reduction", [z["entity_key"] for z in big_zones],
            start_hour=13, end_hour=16,
            reason="Dim large zones during peak; daylight compensates"))

    if not candidates:
        candidates.append(make_action(
            "lighting_reduction",
            [z["entity_key"] for z in zones if z["room_type"] == "hallway"],
            start_hour=max(now_hour, 12), end_hour=min(max(now_hour, 12) + 4, 24),
            reason="Routine optimization: dim circulation lighting"))

    ranked = []
    for action in candidates:
        est = quick_estimate(action, zones)
        d = action.to_dict()
        d.update(est)
        d["reason"] = llm_text(
            f"Rewrite this building-control action reason in one short professional "
            f"sentence: {d['reason']}", d["reason"])
        ranked.append(d)
    ranked.sort(key=lambda a: -a["expected_saving_kwh"])

    # Top actions go to simulation (alerts skip simulation but stay in the plan)
    selected = [a for a in ranked if a["action_type"] != "alert_or_ticket"][:3]
    return {
        "candidate_actions": ranked,
        "ranked_actions": ranked,
        "selected_actions": selected,
    }

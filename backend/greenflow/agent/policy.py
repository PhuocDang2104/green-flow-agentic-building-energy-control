"""Policy Engine: pure-Python guardrail evaluation (no LLM).

Classifies a simulated candidate action as auto_run / approval_required /
rejected with explicit reasons, per REPO_BUILD_SPEC §14.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..config import get_settings
from ..sim.actions import ACTION_RISK
from .regret import regrettable_substitution_check

POLICY_FILE = Path(__file__).with_name("policy.yaml")


@lru_cache
def load_policy() -> dict:
    return yaml.safe_load(POLICY_FILE.read_text(encoding="utf-8"))


def evaluate_action(action: dict, context: dict) -> dict[str, Any]:
    """Evaluate one candidate action against the policy config.

    action: dict form of sim.actions.Action (+ simulation results merged in)
    context keys: zone_types {zone_key: room_type}, occupancy_confidence,
                  forecast_confidence, comfort_risk_after, peak_risk_after,
                  zones_affected, kpi (optional compare_runs dict for the
                  regrettable-substitution check)
    """
    policy = load_policy()
    auto = policy["auto_actions"]
    settings = get_settings()
    reasons: list[str] = []
    violated: list[str] = []

    action_type = action["action_type"]
    risk_level = ACTION_RISK.get(action_type, "medium")

    if action_type in policy.get("rejected_actions", []):
        return _decision("rejected", "high",
                         [f"{action_type} is high-risk: simulation/recommendation only"],
                         ["rejected_actions"])

    # Hard blocks regardless of action class
    zone_types = context.get("zone_types", {})
    blocked = [zk for zk in action.get("target_zone_keys", [])
               if zone_types.get(zk) in auto["blocked_zone_types"]]
    if blocked:
        return _decision("rejected", "high",
                         [f"Target zone(s) {blocked} are in blocked zone types"],
                         ["blocked_zone_types"])

    delta = abs(action.get("setpoint_delta_c") or 0.0)
    if delta > max(auto["max_setpoint_delta_c"], settings.max_setpoint_delta_c):
        return _decision("rejected", "high",
                         [f"Setpoint delta {delta}C exceeds limit "
                          f"{auto['max_setpoint_delta_c']}C"],
                         ["max_setpoint_delta_c"])

    # Approval-required class
    if action_type in policy.get("approval_required_actions", []):
        reasons.append(f"{action_type} is classified as medium-risk: human approval required")
        return _decision("approval_required", risk_level, reasons, [])

    # Auto-run candidates: every guardrail must pass, else escalate to approval.
    # allow_auto_action is the per-run UI switch ("Allow auto-actions"); when the
    # operator unticks it, nothing auto-runs even if every guardrail passes
    # (QC-02 + Human-in-the-Loop guardrail).
    allow_auto = context.get("allow_auto_action", True)
    if not (auto["enabled"] and settings.enable_auto_actions and allow_auto):
        reason = ("Auto-actions disabled for this run by operator" if not allow_auto
                  else "Auto-actions are disabled by configuration")
        return _decision("approval_required", risk_level, [reason], ["auto_disabled"])

    if action_type not in auto["allowed_actions"]:
        reasons.append(f"{action_type} not in auto-allowed list")
        violated.append("allowed_actions")

    occ_conf = context.get("occupancy_confidence", 1.0)
    if occ_conf < max(auto["min_occupancy_confidence"], settings.min_occupancy_confidence):
        reasons.append(f"Occupancy confidence {occ_conf:.2f} below threshold")
        violated.append("min_occupancy_confidence")

    fc_conf = context.get("forecast_confidence", 1.0)
    if fc_conf < auto["min_forecast_confidence"]:
        reasons.append(f"Forecast confidence {fc_conf:.2f} below threshold")
        violated.append("min_forecast_confidence")

    comfort_after = context.get("comfort_risk_after", 0.0)
    if comfort_after > auto["max_comfort_risk_after"]:
        reasons.append(f"Comfort risk after action {comfort_after:.2f} exceeds "
                       f"{auto['max_comfort_risk_after']}")
        violated.append("max_comfort_risk_after")

    peak_after = context.get("peak_risk_after", 0.0)
    if peak_after > auto["max_peak_risk_after"]:
        reasons.append(f"Peak risk after action {peak_after:.2f} exceeds "
                       f"{auto['max_peak_risk_after']}")
        violated.append("max_peak_risk_after")

    zones_affected = context.get("zones_affected",
                                 len(action.get("target_zone_keys", [])) or 99)
    if zones_affected > auto["max_zones_affected"]:
        reasons.append(f"Action affects {zones_affected} zones "
                       f"(limit {auto['max_zones_affected']})")
        violated.append("max_zones_affected")

    not_allowed_types = [zk for zk in action.get("target_zone_keys", [])
                         if zone_types.get(zk) and
                         zone_types[zk] not in auto["allowed_zone_types"]]
    if not_allowed_types:
        reasons.append(f"Zone type not auto-allowed for {not_allowed_types}")
        violated.append("allowed_zone_types")

    # Regrettable substitution: an action that "wins" the target KPI while
    # losing another dimension must never auto-run (spine D8).
    regret = regrettable_substitution_check(
        context.get("kpi", {}), policy.get("regrettable_check"))
    if not regret["passed"]:
        reasons.extend(f["message"] for f in regret["flags"])
        violated.append("regrettable_substitution")

    if violated:
        return _decision("approval_required", risk_level, reasons, violated, regret)

    return _decision("auto_run", "low",
                     [f"{action_type} passes all auto-action guardrails"], [], regret)


def _decision(decision: str, risk_level: str, reasons: list[str],
              violated_rules: list[str],
              regret: dict | None = None) -> dict[str, Any]:
    return {"decision": decision, "risk_level": risk_level,
            "reasons": reasons, "violated_rules": violated_rules,
            "regrettable_check": regret or {"passed": True, "flags": []}}

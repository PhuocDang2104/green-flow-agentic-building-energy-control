"""Action catalog and schedule-override semantics.

Per REPO_BUILD_SPEC §1.1, AI actions never invent physical numbers: an action
only modifies *input schedules* (lighting fraction, setpoints, HVAC
availability). The simulation engine then computes the physical consequences.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# action_type -> default risk classification (policy uses this as a base)
ACTION_RISK = {
    "lighting_reduction": "low",
    "turn_off_non_critical_lighting": "low",
    "hvac_eco_mode": "low",
    "hvac_setback_light": "low",
    "alert_or_ticket": "low",
    "pre_cooling": "medium",
    "early_hvac_shutdown": "medium",
    "ventilation_adjustment": "medium",
    "peak_load_reduction": "medium",
    "demand_response": "medium",
    "whole_building_hvac_shutdown": "high",
}


@dataclass
class Action:
    action_type: str
    target_zone_keys: list[str] = field(default_factory=list)   # empty = all zones
    target_device_keys: list[str] = field(default_factory=list)
    start_hour: float = 0.0
    end_hour: float = 24.0
    # schedule modifiers
    lighting_factor: float | None = None      # multiply lighting schedule
    setpoint_delta_c: float | None = None     # add to cooling setpoint
    hvac_off: bool = False                    # force HVAC unavailable in window
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type,
            "target_zone_keys": self.target_zone_keys,
            "target_device_keys": self.target_device_keys,
            "start_hour": self.start_hour,
            "end_hour": self.end_hour,
            "lighting_factor": self.lighting_factor,
            "setpoint_delta_c": self.setpoint_delta_c,
            "hvac_off": self.hvac_off,
            "reason": self.reason,
            "risk": ACTION_RISK.get(self.action_type, "medium"),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Action":
        return cls(
            action_type=d["action_type"],
            target_zone_keys=d.get("target_zone_keys", []),
            target_device_keys=d.get("target_device_keys", []),
            start_hour=d.get("start_hour", 0.0),
            end_hour=d.get("end_hour", 24.0),
            lighting_factor=d.get("lighting_factor"),
            setpoint_delta_c=d.get("setpoint_delta_c"),
            hvac_off=d.get("hvac_off", False),
            reason=d.get("reason", ""),
        )


def make_action(action_type: str, target_zone_keys: list[str], *,
                start_hour: float = 0.0, end_hour: float = 24.0,
                reason: str = "") -> Action:
    """Factory translating an action type into its schedule modifiers."""
    a = Action(action_type=action_type, target_zone_keys=target_zone_keys,
               start_hour=start_hour, end_hour=end_hour, reason=reason)
    if action_type == "lighting_reduction":
        a.lighting_factor = 0.6
    elif action_type == "turn_off_non_critical_lighting":
        a.lighting_factor = 0.3
    elif action_type == "hvac_eco_mode":
        a.setpoint_delta_c = 1.0
    elif action_type == "hvac_setback_light":
        a.setpoint_delta_c = 0.5
    elif action_type == "pre_cooling":
        a.setpoint_delta_c = -1.0
    elif action_type in ("peak_load_reduction", "demand_response"):
        a.setpoint_delta_c = 1.5
        a.lighting_factor = 0.7
    elif action_type == "early_hvac_shutdown":
        a.hvac_off = True
    elif action_type == "whole_building_hvac_shutdown":
        a.hvac_off = True
    return a


def zone_modifiers_at(actions: list[Action], zone_key: str, hour: float) -> dict:
    """Effective schedule modifiers for one zone at a given hour-of-day."""
    lighting_factor = 1.0
    setpoint_delta = 0.0
    hvac_off = False
    for a in actions:
        if a.target_zone_keys and zone_key not in a.target_zone_keys:
            continue
        if not (a.start_hour <= hour < a.end_hour):
            continue
        if a.lighting_factor is not None:
            lighting_factor = min(lighting_factor, a.lighting_factor)
        if a.setpoint_delta_c is not None:
            setpoint_delta += a.setpoint_delta_c
        hvac_off = hvac_off or a.hvac_off
    return {"lighting_factor": lighting_factor,
            "setpoint_delta_c": setpoint_delta,
            "hvac_off": hvac_off}

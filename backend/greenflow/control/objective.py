"""Objective scoring for receding-horizon control trajectories."""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class ObjectiveWeights:
    energy_cost: float = 1.0
    peak_penalty: float = 6.0
    comfort_penalty: float = 12.0
    ramp_penalty: float = 1.5
    action_change_penalty: float = 0.4
    policy_risk_penalty: float = 5.0

    def to_dict(self) -> dict:
        return asdict(self)


def score_objective(*, energy_kwh: float, peak_kw: float, comfort_minutes: float,
                    ramp_kw: float, action_changes: int, policy_risk: float,
                    weights: ObjectiveWeights | None = None) -> dict:
    w = weights or ObjectiveWeights()
    parts = {
        "energy_cost": energy_kwh * w.energy_cost,
        "peak_penalty": peak_kw * w.peak_penalty,
        "comfort_penalty": comfort_minutes * w.comfort_penalty,
        "ramp_penalty": ramp_kw * w.ramp_penalty,
        "action_change_penalty": float(action_changes) * w.action_change_penalty,
        "policy_risk_penalty": policy_risk * w.policy_risk_penalty,
    }
    parts["score"] = round(sum(parts.values()), 4)
    return {k: round(v, 4) for k, v in parts.items()}


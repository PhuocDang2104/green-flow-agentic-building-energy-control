"""Small helpers for action trajectory payloads."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta


def action_step(*, step: int, start: datetime, step_minutes: int,
                action_type: str, target_zone_keys: list[str],
                setpoint_delta_c: float = 0.0,
                lighting_factor: float | None = None,
                reason: str = "") -> dict:
    return {
        "step": step,
        "start": start.isoformat(),
        "end": (start + timedelta(minutes=step_minutes)).isoformat(),
        "action_type": action_type,
        "target_zone_keys": target_zone_keys,
        "setpoint_delta_c": round(float(setpoint_delta_c), 3),
        "lighting_factor": lighting_factor,
        "reason": reason,
    }


def trajectory(name: str, horizon_start: datetime, horizon_steps: int,
               step_minutes: int, actions: list[dict], strategy: str) -> dict:
    return {
        "trajectory_id": f"traj_{uuid.uuid4().hex[:10]}",
        "name": name,
        "strategy": strategy,
        "horizon_start": horizon_start.isoformat(),
        "horizon_steps": horizon_steps,
        "step_minutes": step_minutes,
        "actions": actions,
        "execute_step": 1,
    }


"""Apply agent actions to an IDF file by rewriting schedules only.

Used by the real-EnergyPlus path. The counterpart for the synthetic engine is
`actions.zone_modifiers_at`. Both implement the same semantics: actions touch
schedules (lighting fraction, cooling setpoint), never physics.
"""

from __future__ import annotations

import re
from pathlib import Path

from .actions import Action


def apply_actions_to_idf(idf_text: str, actions: list[Action]) -> str:
    """Return IDF text with action schedule overrides applied.

    MVP approach: global schedule rewrites (the archetype shares WorkHoursFrac
    and CoolSetSched across zones). Zone-scoped actions in the E+ path would
    require splitting schedules per zone — P1.
    """
    out = idf_text
    for action in actions:
        if action.lighting_factor is not None:
            out = _scale_schedule_window(out, "WorkHoursFrac",
                                         action.start_hour, action.end_hour,
                                         action.lighting_factor)
        if action.setpoint_delta_c:
            out = _shift_schedule_window(out, "CoolSetSched",
                                         action.start_hour, action.end_hour,
                                         action.setpoint_delta_c)
    return out


def _patch_schedule(idf_text: str, schedule_name: str, start_hour: float,
                    end_hour: float, fn) -> str:
    """Apply fn(value) to schedule values whose Until hour falls in the window."""
    pattern = re.compile(
        r"(SCHEDULE:COMPACT,\s*" + re.escape(schedule_name) + r"\s*,.*?;)",
        re.IGNORECASE | re.DOTALL)
    m = pattern.search(idf_text)
    if not m:
        return idf_text
    block = m.group(1)
    # Each "Until: HH:00, value" covers (prev_until, HH]; patch every segment
    # overlapping the action window. The value may be separated from the time
    # by an "!-" comment line.
    until_re = re.compile(
        r"(Until:\s*(\d+):00\s*,(?:[^\S\n]*!-[^\n]*)?\s*)([-\d.eE]+)")
    prev_hour = 0.0
    out_parts: list[str] = []
    pos = 0
    for um in until_re.finditer(block):
        hour = int(um.group(2))
        if hour <= prev_hour:  # new For: day-block restarts the day
            prev_hour = 0.0
        overlaps = hour > start_hour and prev_hour < end_hour
        prev_hour = hour
        out_parts.append(block[pos:um.start()])
        if overlaps:
            out_parts.append(um.group(1) + f"{fn(float(um.group(3))):g}")
        else:
            out_parts.append(um.group(0))
        pos = um.end()
    out_parts.append(block[pos:])
    return idf_text.replace(block, "".join(out_parts))


def _scale_schedule_window(idf_text: str, schedule_name: str,
                           start_hour: float, end_hour: float,
                           factor: float) -> str:
    return _patch_schedule(idf_text, schedule_name, start_hour, end_hour,
                           lambda v: round(v * factor, 4))


def _shift_schedule_window(idf_text: str, schedule_name: str,
                           start_hour: float, end_hour: float,
                           delta: float) -> str:
    return _patch_schedule(idf_text, schedule_name, start_hour, end_hour,
                           lambda v: round(v + delta, 2))


def write_variant_idf(source: str | Path, dest: str | Path,
                      actions: list[Action]) -> Path:
    text = Path(source).read_text(encoding="utf-8", errors="replace")
    patched = apply_actions_to_idf(text, actions)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(patched, encoding="utf-8")
    return dest

"""Run an agent-variant simulation (baseline + demo action plan) and persist
the comparison KPI.

Usage: python scripts/run_agent_variant.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from greenflow.agent.tools.simulation_tool import simulate_actions  # noqa: E402
from greenflow.config import get_settings  # noqa: E402
from greenflow.sim.actions import make_action  # noqa: E402


def main() -> None:
    actions = [
        make_action("lighting_reduction",
                    ["zone_storey0_open_office", "zone_storey0_circulation"],
                    start_hour=12, end_hour=18,
                    reason="Daylight dimming in large zones"),
        make_action("hvac_eco_mode", [], start_hour=13, end_hour=16,
                    reason="Peak window setpoint relaxation"),
        make_action("pre_cooling", [], start_hour=11, end_hour=13,
                    reason="Pre-charge thermal mass"),
    ]
    result = simulate_actions(get_settings().default_building_id, actions,
                              persist=True, run_kind="agent")
    print(json.dumps(result["kpi"], indent=2))


if __name__ == "__main__":
    main()

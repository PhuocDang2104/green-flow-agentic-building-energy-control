"""Run a baseline simulation and persist it (EnergyPlus if configured,
synthetic otherwise).

Usage: python scripts/run_baseline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from greenflow.agent.tools.simulation_tool import load_normalized, simulate_actions  # noqa: E402
from greenflow.config import get_settings  # noqa: E402
from greenflow.sim.runner import energyplus_available  # noqa: E402


def main() -> None:
    settings = get_settings()
    engine = "EnergyPlus" if energyplus_available() else "synthetic (no ENERGYPLUS_BIN)"
    print(f"Engine: {engine}")
    result = simulate_actions(settings.default_building_id, [], persist=True,
                              run_kind="baseline")
    print("Baseline run persisted.")
    print("KPI vs itself (sanity):", result["kpi"]["baseline_kwh"], "kWh/day")


if __name__ == "__main__":
    main()

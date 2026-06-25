"""Climate scenario (El Niño heat-stress) — save + run-IDF endpoints.

The frontend never rewrites the baseline IDF; it POSTs a scenario config here.
`run-idf` currently returns a transparent **surrogate** building response derived
from the scenario deltas (so it works without a live EnergyPlus install); the
payload + return shape match the spec so a real EnergyPlus run can be dropped in
behind the same endpoint later. Scenarios are persisted to storage as JSON; run
results are cached in-process and exposed by run_id.
"""
from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...config import get_settings

router = APIRouter()

# in-process cache of run results (run_id -> result dict)
_RUNS: dict[str, dict] = {}

# rough building constants for the surrogate (demo building)
_BASE_PEAK_KW = 66.6
_N_ZONES = 14


class ClimateScenario(BaseModel):
    scenario_id: str = "el_nino_heat_stress"
    location: str = "Hanoi"
    outdoor_temp_delta_c: float = 0.0
    relative_humidity_delta_pct: float = 0.0
    solar_multiplier: float = 1.0
    wind_speed_ms: float = 2.5
    wind_direction_deg: float = 135.0
    cooling_stress_factor: float = 1.0
    comfort_drift_c: float = 0.0


def _scenario_dir():
    d = get_settings().storage_path / "processed" / "scenarios"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/scenarios/save")
def save_scenario(scenario: ClimateScenario):
    path = _scenario_dir() / f"{scenario.scenario_id}.json"
    path.write_text(json.dumps(scenario.model_dump(), indent=2), encoding="utf-8")
    return {"saved": True, "scenario_id": scenario.scenario_id, "path": str(path)}


def _surrogate_response(s: ClimateScenario) -> dict:
    """Transparent heuristic building response (no EnergyPlus needed)."""
    uplift = round((s.cooling_stress_factor - 1.0) * 100, 1)
    peak_change = round(uplift / 100.0 * _BASE_PEAK_KW * 0.62, 1)
    comfort_zones = max(0, min(_N_ZONES, round(s.comfort_drift_c * 2.4)))
    if s.wind_speed_ms >= 3:
        relief = "Good relief"
    elif s.wind_speed_ms >= 1.5:
        relief = "Low relief"
    else:
        relief = "Stagnant"
    return {
        "hvac_load_uplift_pct": uplift,
        "peak_demand_change_kw": peak_change,
        "comfort_risk_zones": comfort_zones,
        "zone_temp_drift_c": round(s.comfort_drift_c, 2),
        "ventilation_relief_level": relief,
        "engine": "surrogate_v1",
        "note": "Heuristic estimate from scenario deltas; not a full EnergyPlus run.",
    }


@router.post("/simulations/run-idf")
def run_idf(scenario: ClimateScenario):
    run_id = f"clim_{uuid.uuid4().hex[:10]}"
    result = _surrogate_response(scenario)
    _RUNS[run_id] = {"run_id": run_id, "created_at": time.time(),
                     "scenario": scenario.model_dump(), **result}
    # also persist the scenario that was run
    try:
        save_scenario(scenario)
    except Exception:
        pass
    return _RUNS[run_id]


@router.get("/simulations/run-idf/{run_id}/result")
def run_idf_result(run_id: str):
    if run_id not in _RUNS:
        raise HTTPException(404, f"run '{run_id}' not found")
    return _RUNS[run_id]

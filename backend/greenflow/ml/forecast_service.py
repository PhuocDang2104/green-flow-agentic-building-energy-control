"""ForecastService — LightGBM surrogate wrapper (spine merge, not yet wired).

The real-data pipeline (tools/ in the VinHack workspace) trained a LightGBM
surrogate on EnergyPlus zone telemetry with R2 = 0.95 (HVAC power) / 0.94
(zone temp). This module is the landing spot for wrapping that model as a
service the Prediction/Control agents can call, replacing the current
heuristic in agent/nodes/prediction.py when the model files are present.

Implementation contract (spine docs/spine/DECISIONS_AND_CRITIQUE.md D10, D11):

1. train_surrogate (separate script): persist to storage/models/
     surrogate_hvac_v1.txt / surrogate_temp_v1.txt   (lgb.Booster.save_model)
     surrogate_meta_v1.json                          (ordered feature list,
        validation metrics, residual_sigma per (room_type, hour) bucket,
        partial dependence of cooling setpoint)
   D11 trap: baseline data has almost no setpoint variance. If the setpoint
   partial dependence is flat, what-if scoring is meaningless — fail at train
   time (raise), not at demo time. Fix by adding 2-3 EnergyPlus runs at
   setpoints 23/25/26 C to the training set.

2. Confidence (D10): residual-sigma per bucket, computed on the validation
   split at train time:
     yhat_lower = yhat - 1.64 * sigma_bucket
     yhat_upper = yhat + 1.64 * sigma_bucket
     confidence = clip(1 - sigma_bucket / (|yhat| + eps), 0, 1)

3. what_if(): baseline vs override trajectories for action scoring — no DB
   writes. forecast(): full horizon forecast persisted to forecast_runs /
   forecast_predictions (schema already has both tables).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[3] / "storage" / "models"


@dataclass
class WhatIfResult:
    zone_key: str
    target: str                      # hvac_power_kw | temperature_c
    timestamps: list[datetime]
    baseline: list[float]
    override: list[float]
    confidence: float


class ForecastService:
    def __init__(self, hvac_model, temp_model, meta: dict):
        self.hvac_model = hvac_model
        self.temp_model = temp_model
        self.meta = meta

    @classmethod
    def load_default(cls, model_dir: Path = MODEL_DIR) -> "ForecastService":
        raise NotImplementedError("load lgb.Booster + meta JSON — see module docstring")

    def what_if(self, zone_key: str, start: datetime, horizon_minutes: int,
                overrides: dict) -> list[WhatIfResult]:
        """overrides: {"setpoint_delta_c": +1.5, "lighting_factor": 0.3}."""
        raise NotImplementedError

    def forecast(self, conn, building_id, zone_keys: list[str],
                 issued_ts: datetime, horizon_minutes: int = 240) -> str:
        """Persist to forecast_runs + forecast_predictions, return run id."""
        raise NotImplementedError

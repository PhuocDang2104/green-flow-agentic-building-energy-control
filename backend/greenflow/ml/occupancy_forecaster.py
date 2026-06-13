"""Occupancy forecaster — seasonal profile + optional residual model (spine merge).

Feeds three consumers: the empty-zone rule (will the zone refill soon?),
pre-cooling lead-time decisions (tomorrow hot + high occupancy), and building
demand forecast (sum of zones x surrogate -> peak risk).

Architecture (deliberately simple, robust for the demo):
1. Seasonal profile: median occupancy_count per
   (zone, daytype in {workday, sat, sun_holiday}, 15-min slot 0..95),
   one GROUP BY over telemetry_zone_15m / occupancy_zone_15m.
2. Optional LightGBM residual model on top (lags, same-slot yesterday).
   If time is short the profile alone demos fine — the telemetry is
   schedule-generated, so the profile fits well. Say so honestly in the
   pitch; do not oversell it as deep learning.
3. Confidence from the historical IQR of the bucket:
   confidence = 1 - IQR / (median + 1). Sensor-dropout scenarios halve it.

Outputs go through forecast_runs / forecast_predictions with
target_name='occupancy_count'.
"""

from __future__ import annotations

from datetime import datetime


class OccupancyForecaster:
    @classmethod
    def fit_profiles(cls, conn, building_id) -> "OccupancyForecaster":
        raise NotImplementedError("one GROUP BY query — see module docstring")

    def forecast(self, conn, building_id, zone_keys: list[str],
                 issued_ts: datetime, horizon_minutes: int = 1440) -> str:
        raise NotImplementedError

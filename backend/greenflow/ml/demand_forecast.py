"""Dataset-aligned day-ahead facility and HVAC demand forecast.

Both curves use the production registry models trained on the active 308-zone
El Nino data contract.  Facility demand comes from the building model; HVAC is
the sum of per-zone HVAC predictions.  The function never relabels HVAC as the
whole-building load.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from ..config import get_settings
from ..datasets import active_dataset
from ..db import fetch_all
from .model_registry import load_model

WORK_START, WORK_END = 7, 19
PEAK_START, PEAK_END = 13, 17
HEATWAVE_C = 35.0


def _setpoint(index) -> np.ndarray:
    # Matches the active EnergyPlus schedule regimes in the training package.
    return np.array([25.0 if WORK_START <= ts.hour < WORK_END else 30.0 for ts in index])


def _default_weather(index) -> dict[str, np.ndarray]:
    hour = np.array([ts.hour + ts.minute / 60 for ts in index])
    return {
        "outdoor_temp_c": 30.0 + 4.5 * np.sin(2 * np.pi * (hour - 9.5) / 24),
        "outdoor_rh_pct": np.clip(
            70 - 10 * np.sin(2 * np.pi * (hour - 9.5) / 24), 45, 95
        ),
        "global_horizontal_radiation_wh_m2": np.clip(
            900 * np.sin(np.pi * (hour - 6) / 12.5), 0, None
        ),
        "wind_speed_m_s": np.full(len(index), 2.0),
        "cloud_cover_pct": np.full(len(index), 40.0),
    }


def _weather(conn, index, shift: float) -> dict[str, np.ndarray]:
    values = _default_weather(index)
    if not index:
        return values
    rows = fetch_all(conn, """
        SELECT timestamp, outdoor_temp_c, humidity_pct, wind_speed_mps,
               cloud_cover_pct, solar_w_m2
        FROM weather_15m
        WHERE timestamp >= :start AND timestamp <= :end
        ORDER BY timestamp
    """, start=index[0], end=index[-1])
    by_time = {
        row["timestamp"].astimezone(index[0].tzinfo).replace(second=0, microsecond=0): row
        for row in rows
    }
    for position, ts in enumerate(index):
        row = by_time.get(ts.replace(second=0, microsecond=0))
        if not row:
            continue
        mapping = {
            "outdoor_temp_c": "outdoor_temp_c",
            "outdoor_rh_pct": "humidity_pct",
            "wind_speed_m_s": "wind_speed_mps",
            "cloud_cover_pct": "cloud_cover_pct",
            "global_horizontal_radiation_wh_m2": "solar_w_m2",
        }
        for feature, column in mapping.items():
            if row.get(column) is not None:
                value = float(row[column])
                if feature == "global_horizontal_radiation_wh_m2":
                    value *= active_dataset().timestep_minutes / 60.0
                values[feature][position] = value
    values["outdoor_temp_c"] += shift
    return values


def _time_features(index, weather) -> dict:
    hour = np.array([ts.hour + ts.minute / 60 for ts in index])
    dow = np.array([ts.weekday() for ts in index])
    month = np.array([ts.month for ts in index])
    return {
        **weather,
        "hour_sin": np.sin(2 * np.pi * hour / 24),
        "hour_cos": np.cos(2 * np.pi * hour / 24),
        "dayofweek_sin": np.sin(2 * np.pi * dow / 7),
        "dayofweek_cos": np.cos(2 * np.pi * dow / 7),
        "month_sin": np.sin(2 * np.pi * month / 12),
        "month_cos": np.cos(2 * np.pi * month / 12),
        "office_hours_flag": np.array([
            1 if ts.weekday() < 5 and WORK_START <= ts.hour < WORK_END else 0
            for ts in index
        ]),
    }


def _frame(features: list[str], full: dict):
    import pandas as pd

    return pd.DataFrame({feature: full[feature] for feature in features})


def _building_curve(model, index, weather, setpoint, detailed_area_m2):
    full = _time_features(index, weather)
    full.update({
        "avg_setpoint_c": setpoint,
        "detailed_area_m2": np.full(len(index), detailed_area_m2),
    })
    return np.clip(model.model.predict(_frame(model.features, full)), 0, None)


def _hvac_curve(model, zones, index, weather, setpoint):
    n_zones, n_steps = len(zones), len(index)
    time = _time_features(index, weather)
    full = {
        key: np.tile(value, n_zones) for key, value in time.items()
    }
    area = np.repeat([float(zone["area_m2"] or 50.0) for zone in zones], n_steps)
    volume = np.repeat([
        float(zone["volume_m3"] or (float(zone["area_m2"] or 50.0) * 3.0))
        for zone in zones
    ], n_steps)
    height = np.divide(volume, np.maximum(area, 0.1))
    full.update({
        "cooling_setpoint_c": np.tile(setpoint, n_zones),
        "area_m2_final": area, "volume_m3_final": volume, "height_m_final": height,
        # Backward-compatible aliases for an older local fallback artifact.
        "area_m2": area, "volume_m3": volume, "ceiling_height_m": height,
    })
    prediction = np.clip(model.model.predict(_frame(model.features, full)), 0, None)
    return prediction.reshape(n_zones, n_steps).sum(axis=0)


def forecast_building(
    conn, building_id, issued_ts: datetime, horizon_h: int = 24, weather_shift: float = 0.0
) -> dict:
    dataset = active_dataset()
    building_model = load_model("building")
    hvac_model = load_model("hvac")
    if building_model is None or building_model.model is None:
        return {"error": "dataset-aligned building model is unavailable"}
    if hvac_model is None or hvac_model.model is None:
        return {"error": "dataset-aligned HVAC model is unavailable"}

    zones = fetch_all(conn, """
        SELECT entity_key, room_type, area_m2, volume_m3
        FROM zones WHERE building_id = :building_id ORDER BY entity_key
    """, building_id=building_id)
    if len(zones) != dataset.expected_zones:
        return {"error": f"expected {dataset.expected_zones} zones, found {len(zones)}"}

    step_minutes = dataset.timestep_minutes
    steps = max(1, int(horizon_h * 60 / step_minutes))
    index = [issued_ts + timedelta(minutes=step_minutes * (step + 1)) for step in range(steps)]
    model_index = [issued_ts, *index]
    weather = _weather(conn, model_index, weather_shift)
    current_rows = fetch_all(conn, """
        SELECT sum(total_power_kw) AS total_kw, sum(hvac_power_kw) AS hvac_kw,
               avg(setpoint_c) AS avg_setpoint_c
        FROM telemetry_zone_15m
        WHERE building_id = :building_id AND timestamp = (
            SELECT max(timestamp) FROM telemetry_zone_15m
            WHERE building_id = :building_id AND timestamp <= :issued_at
        )
    """, building_id=building_id, issued_at=issued_ts)
    current = current_rows[0] if current_rows else {}
    future_setpoint = _setpoint(index)
    current_setpoint = float(current.get("avg_setpoint_c") or future_setpoint[0])
    setpoint = np.concatenate(([current_setpoint], future_setpoint))
    detailed_area = sum(
        float(zone["area_m2"] or 0.0)
        for zone in zones
        if zone["room_type"] != "gross_area_placeholder"
    )
    raw_total = _building_curve(
        building_model, model_index, weather, setpoint, detailed_area
    )
    raw_hvac = _hvac_curve(hvac_model, zones, model_index, weather, setpoint)
    current_total = float(current.get("total_kw") or raw_total[0])
    current_hvac = float(current.get("hvac_kw") or raw_hvac[0])
    total_factor = float(np.clip(current_total / max(raw_total[0], 0.1), 0.5, 1.5))
    hvac_factor = float(np.clip(current_hvac / max(raw_hvac[0], 0.1), 0.5, 3.0))
    total_kw = raw_total[1:] * total_factor
    hvac_kw = raw_hvac[1:] * hvac_factor

    peak_index = int(np.argmax(total_kw))
    peak_total = float(total_kw[peak_index])
    peak_hvac = float(hvac_kw[peak_index])
    peak_ts = index[peak_index]
    peak_window = np.array([PEAK_START <= ts.hour < PEAK_END for ts in index])
    heatwave = bool(
        peak_window.any()
        and float(weather["outdoor_temp_c"][1:][peak_window].max()) >= HEATWAVE_C
    )
    recommend_precool = heatwave or PEAK_START <= peak_ts.hour < PEAK_END

    capacity = max(1.0, get_settings().greenflow_contracted_demand_kw)
    utilization = peak_total / capacity
    return {
        "issued_at": str(issued_ts), "horizon_hours": horizon_h,
        "step_minutes": step_minutes, "zone_count": len(zones),
        "peak_total_kw": round(peak_total, 1), "peak_hvac_kw": round(peak_hvac, 1),
        "peak_at": str(peak_ts), "peak_hour": peak_ts.hour,
        "contracted_demand_kw": capacity,
        "peak_utilization": round(utilization, 3),
        "peak_level": "high" if utilization >= 0.85 else "watch" if utilization >= 0.6 else "normal",
        "recommend_precool": recommend_precool,
        "precool_window": {"start_hour": 6, "end_hour": 8} if recommend_precool else None,
        "series": [
            {"ts": str(ts), "total_kw": round(float(total), 1),
             "hvac_kw": round(float(hvac), 1)}
            for ts, total, hvac in zip(index, total_kw, hvac_kw)
        ],
        "models": {
            "building": building_model.metadata(), "hvac": hvac_model.metadata(),
        },
        "calibration": {
            "measured_total_kw": round(current_total, 2),
            "raw_model_total_kw": round(float(raw_total[0]), 2),
            "total_factor": round(total_factor, 4),
            "measured_hvac_kw": round(current_hvac, 2),
            "raw_model_hvac_kw": round(float(raw_hvac[0]), 2),
            "hvac_factor": round(hvac_factor, 4),
        },
        "dataset": dataset.to_metadata(),
        "alerts": [
            f"Pre-cool recommended before the {peak_total:.0f} kW facility peak at "
            f"{peak_ts:%H:%M}."
        ] if recommend_precool else [],
    }

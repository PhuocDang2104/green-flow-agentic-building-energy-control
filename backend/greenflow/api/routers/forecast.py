"""Forecast APIs for the dashboard: day-ahead HVAC demand/peak (pre-cool) and
learned occupancy profile.

Both endpoints surface the `ml` package directly so Tab 2 cards (peak forecast,
demand curve, occupancy) have a data source. The surrogate forecast needs the
`ml` extra + a trained model; without them we return 503 instead of guessing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from ...db import db_conn, fetch_all
from ...replayclock import anchor
from ..deps import default_building_id

router = APIRouter()

TZ = timezone(timedelta(hours=7))


@router.get("/ml/model-info")
def model_info():
    """Forecast models + held-out metrics, mirrored from the MLflow registry
    (greenflow_surrogate_*). Reads the committed model meta so it never depends on
    MLflow being reachable at request time."""
    from ...ml import realforecast
    models = realforecast.test_metrics() or {}
    out = []
    for key, m in models.items():
        out.append({
            "registry_name": f"greenflow_surrogate_{key}",
            "target": m.get("target"),
            "metrics": m.get("test_metrics", {}),
            "n_features": len(m.get("features", [])),
            "split": m.get("split", "seasonal holdout (cool months)"),
            "top_features": [t["f"] for t in (m.get("top_features") or [])[:5]],
        })
    return {
        "registry": "MLflow · experiment greenflow-surrogate",
        "engine": "LightGBM surrogate (EnergyPlus + Open-Meteo 2025, 30-min)",
        "models": out,
        "derived": {
            "comfort_risk": "rule: zone temp > 26.5°C while occupied",
            "peak_risk": "rule: zone power vs peak threshold",
            "temperature_c": "DoE thermal surrogate (no real target in the training set)",
        },
    }


@router.get("/forecast/demand")
def demand_forecast(building_id: str = Query(default=None),
                    horizon_h: int = Query(default=24, ge=1, le=72),
                    weather_shift: float = Query(default=0.0, ge=-10, le=10)):
    """Day-ahead building HVAC demand + peak + structured pre-cool recommendation.

    `weather_shift` (°C) is a what-if knob (e.g. +3 = heatwave) for the curve.
    """
    try:
        from ...ml.demand_forecast import forecast_building
    except ImportError:
        raise HTTPException(503, "ml extra not installed (pip install '.[ml]')")

    b = building_id or default_building_id()
    with db_conn() as conn:
        result = forecast_building(conn, b, anchor(conn, b),
                                   horizon_h=horizon_h, weather_shift=weather_shift)
    if result.get("error"):
        raise HTTPException(503, result["error"])
    result["building_id"] = b
    return result


@router.get("/forecast/occupancy")
def occupancy_forecast(building_id: str = Query(default=None),
                       horizon_h: int = Query(default=24, ge=1, le=72),
                       step_min: int = Query(default=60, ge=15, le=120)):
    """Expected occupancy per zone over the horizon, from the learned profile
    (median telemetry by zone × daytype × 15-min slot). Deterministic, not ML —
    real-time occupancy comes from YOLO elsewhere."""
    try:
        from ...ml.occupancy_profile import OccupancyProfile
    except ImportError:
        raise HTTPException(503, "ml extra not installed (pip install '.[ml]')")

    b = building_id or default_building_id()
    issued = anchor(building_id=b)
    n = int(horizon_h * 60 / step_min)
    index = [issued + timedelta(minutes=step_min * i) for i in range(n)]

    with db_conn() as conn:
        profile = OccupancyProfile.learn(conn, b)
        zones = fetch_all(conn, "SELECT entity_key, name, room_type, area_m2 "
                          "FROM zones WHERE building_id = :b ORDER BY name", b=b)

    zone_series, building_total = [], [0.0] * n
    for z in zones:
        ek = z["entity_key"]
        cap = profile.meta.get(ek, {}).get("capacity")
        series = []
        for i, ts in enumerate(index):
            e = profile.expected(ek, ts)
            building_total[i] += e["count"]
            series.append({"ts": str(ts), "frac": e["frac"],
                           "count": e["count"], "confidence": e["confidence"]})
        zone_series.append({
            "entity_key": ek, "name": z["name"], "room_type": z["room_type"],
            "capacity": round(cap, 1) if cap else None, "series": series,
        })

    return {
        "building_id": b, "issued_at": str(issued),
        "horizon_hours": horizon_h, "step_minutes": step_min,
        "zones": zone_series,
        "building_series": [{"ts": str(ts), "occupancy": int(c)}
                            for ts, c in zip(index, building_total)],
    }

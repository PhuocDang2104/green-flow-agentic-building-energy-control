"""Dataset-aligned day-ahead forecast calibration and coverage."""

from datetime import datetime, timedelta, timezone

import numpy as np

from greenflow.ml import demand_forecast


class FakeModel:
    model = object()
    features = []

    def metadata(self):
        return {"source": "test", "dataset": {"dataset_key": "elnino_2024_mar_apr"}}


def test_forecast_covers_308_zones_and_anchors_to_current_meter(monkeypatch):
    zones = [
        {"entity_key": f"zone-{index}", "room_type": "workspace",
         "area_m2": 50.0, "volume_m3": 150.0}
        for index in range(308)
    ]
    current = [{"total_kw": 840.0, "hvac_kw": 250.0, "avg_setpoint_c": 25.0}]

    def fake_fetch_all(_conn, sql, **_params):
        return zones if "FROM zones" in sql else current

    def fake_weather(_conn, index, _shift):
        return {
            "outdoor_temp_c": np.full(len(index), 34.0),
            "outdoor_rh_pct": np.full(len(index), 60.0),
            "global_horizontal_radiation_wh_m2": np.full(len(index), 200.0),
            "wind_speed_m_s": np.full(len(index), 2.0),
            "cloud_cover_pct": np.full(len(index), 40.0),
        }

    monkeypatch.setattr(demand_forecast, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(demand_forecast, "load_model", lambda _kind: FakeModel())
    monkeypatch.setattr(demand_forecast, "_weather", fake_weather)
    monkeypatch.setattr(
        demand_forecast, "_building_curve",
        lambda *_args: np.array([700.0, 710.0, 720.0]),
    )
    monkeypatch.setattr(
        demand_forecast, "_hvac_curve",
        lambda *_args: np.array([100.0, 105.0, 110.0]),
    )

    issued = datetime(2024, 4, 17, 15, tzinfo=timezone(timedelta(hours=7)))
    result = demand_forecast.forecast_building(object(), "building", issued, horizon_h=1)

    assert result["zone_count"] == 308
    assert result["step_minutes"] == 30
    assert len(result["series"]) == 2
    assert result["calibration"]["total_factor"] == 1.2
    assert result["calibration"]["hvac_factor"] == 2.5
    assert result["peak_total_kw"] == 864.0
    assert result["peak_hvac_kw"] == 275.0

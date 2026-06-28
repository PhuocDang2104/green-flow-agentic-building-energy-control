"""The agent headline must forecast the requested horizon, not always t+1."""

from contextlib import contextmanager
from datetime import datetime, timezone

from greenflow import db
from greenflow.agent.nodes import prediction
from greenflow.ml import forecast_lag


def test_lag_forecast_rolls_two_steps_for_sixty_minutes(monkeypatch):
    rows = []
    for key, base in (("zone-a", 10.0), ("zone-b", 20.0)):
        for step in range(4):
            rows.append({"k": key, "ts": step, "p": base + step, "occ": 5.0})

    @contextmanager
    def fake_db_conn():
        yield object()

    def fake_fetch_all(_conn, sql, **_params):
        return [{"o": 31.0}] if "weather_15m" in sql else rows

    def fake_rollout(history, exogenous):
        assert len(exogenous) == 2
        return [(item[2], history[-1] + index + 1) for index, item in enumerate(exogenous)]

    monkeypatch.setattr(db, "db_conn", fake_db_conn)
    monkeypatch.setattr(db, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(forecast_lag, "available", lambda: True)
    monkeypatch.setattr(forecast_lag, "predict_day_ahead", fake_rollout)

    result = prediction._ml_building_forecast(
        "building", datetime(2024, 4, 17, 15, tzinfo=timezone.utc), 60
    )

    assert result["forecast_horizon_minutes"] == 60
    assert result["zone_count"] == 2
    assert result["zone_forecast_kw"] == {"zone-a": 15.0, "zone-b": 25.0}
    assert result["building_next_kw"] == 40.0

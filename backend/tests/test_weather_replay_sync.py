from contextlib import contextmanager
from datetime import datetime, timezone

from greenflow.agent.tools import db_tool
from greenflow.api import ws


@contextmanager
def _connection():
    yield object()


def test_latest_weather_is_bounded_by_replay_anchor(monkeypatch):
    replay_at = datetime(2024, 4, 17, 8, 0, tzinfo=timezone.utc)
    captured = {}

    def fake_fetch_one(_conn, sql, **params):
        captured["sql"] = sql
        captured["params"] = params
        return {"timestamp": replay_at, "outdoor_temp_c": 35.2}

    monkeypatch.setattr(db_tool, "db_conn", _connection)
    monkeypatch.setattr(db_tool, "fetch_one", fake_fetch_one)

    result = db_tool.get_latest_weather(at=replay_at)

    assert "timestamp <= :replay_at" in captured["sql"]
    assert captured["params"]["replay_at"] == replay_at
    assert result["timestamp"] == replay_at.isoformat()


def test_websocket_weather_uses_state_tick_timestamp(monkeypatch):
    captured = {}

    def fake_fetch_all(_conn, sql, **params):
        captured["sql"] = sql
        captured["params"] = params
        return [{"timestamp": "2024-04-17T15:00:00+07:00", "humidity_pct": 68}]

    monkeypatch.setattr(ws, "db_conn", _connection)
    monkeypatch.setattr(ws, "fetch_all", fake_fetch_all)

    result = ws._weather_at("2024-04-17T15:00:00+07:00")

    assert "timestamp <= cast(:ts as timestamptz)" in captured["sql"]
    assert captured["params"]["ts"] == "2024-04-17T15:00:00+07:00"
    assert result["humidity_pct"] == 68

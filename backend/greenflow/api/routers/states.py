"""Live state / time-series / KPI APIs."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ...agent.tools import db_tool, timeseries_tool
from ...agent.tools.db_tool import _clean
from ...db import db_conn, fetch_all
from ...replayclock import anchor
from ..deps import default_building_id, resolve_zone

router = APIRouter()


@router.get("/state/latest")
def latest_state(building_id: str = Query(default=None)):
    b = building_id or default_building_id()
    return {
        "zones": db_tool.get_latest_zone_state(b),
        "devices": db_tool.get_latest_device_state(b),
        "weather": db_tool.get_latest_weather(building_id=b),
    }


@router.get("/weather/current")
def current_weather(building_id: str = Query(default=None)):
    """Read-only weather snapshot aligned to the dashboard replay clock."""
    b = building_id or default_building_id()
    with db_conn() as conn:
        replay_at = anchor(conn, b)
    return {
        "replay_at": replay_at.isoformat(),
        **db_tool.get_latest_weather(at=replay_at, building_id=b),
    }


@router.get("/timeseries")
def timeseries(zone: str, hours: int = 24, building_id: str = Query(default=None)):
    z = resolve_zone(zone, building_id or default_building_id())
    return timeseries_tool.get_zone_history(str(z["building_id"]), str(z["id"]), hours)


@router.get("/timeseries/building")
def building_timeseries(hours: int = 24, building_id: str = Query(default=None)):
    b = building_id or default_building_id()
    with db_conn() as conn:
        return [_clean(r) for r in fetch_all(conn, f"""
            SELECT timestamp,
                   sum(total_power_kw) AS total_power_kw,
                   sum(hvac_power_kw) AS hvac_power_kw,
                   sum(lighting_power_kw) AS lighting_power_kw,
                   sum(plug_power_kw) AS plug_power_kw,
                   sum(occupancy_count) AS occupancy
            FROM telemetry_zone_15m
            WHERE building_id = :b AND timestamp > :anchor - interval '{int(hours)} hours'
              AND timestamp <= :anchor
            GROUP BY timestamp ORDER BY timestamp
        """, b=b, anchor=anchor(conn, b))]


@router.get("/kpi/current")
def current_kpis(building_id: str = Query(default=None)):
    return timeseries_tool.get_building_kpis(building_id or default_building_id())


@router.get("/kpi/health-score")
def health_score(building_id: str = Query(default=None)):
    """Composite building-health score (0-100) + per-dimension breakdown."""
    return timeseries_tool.get_building_health(building_id or default_building_id())

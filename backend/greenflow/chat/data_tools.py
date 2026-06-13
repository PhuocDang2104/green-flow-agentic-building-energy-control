"""Tools truy vấn LỊCH SỬ tòa nhà cho LLM gọi (function-calling).

Nguyên tắc an toàn: LLM KHÔNG sinh SQL tự do. Mỗi tool là 1 query THAM SỐ HOÁ
cố định, chỉ nhận tham số có kiểu/whitelist -> không injection, không quét bậy.
LLM chỉ chọn tool + điền tham số; thực thi là code này.

"Bây giờ" = replay clock = max(timestamp) trong telemetry (dữ liệu là quá khứ).
"""
from __future__ import annotations

from greenflow.db import fetch_all, fetch_one

WINDOW_INTERVAL = {"day": "1 day", "week": "7 days", "month": "30 days"}
ZONE_METRICS = {"total_power_kw", "hvac_power_kw", "lighting_power_kw",
                "temperature_c", "co2_ppm", "occupancy_count", "cost_vnd"}


def _now(conn, building_id):
    row = fetch_one(conn, "SELECT max(timestamp) AS ts FROM telemetry_zone_15m "
                    "WHERE building_id = :b", b=building_id)
    return row["ts"] if row else None


def get_building_kpi(conn, building_id, window: str = "day") -> dict:
    iv = WINDOW_INTERVAL.get(window, "1 day")
    now = _now(conn, building_id)
    if now is None:
        return {"error": "no data"}
    row = fetch_one(conn, f"""
        WITH w AS (SELECT * FROM telemetry_zone_15m
                   WHERE building_id = :b AND timestamp > :now - interval '{iv}'
                     AND timestamp <= :now),
             peak AS (SELECT timestamp, sum(total_power_kw) kw FROM w GROUP BY 1)
        SELECT round(sum(energy_kwh)::numeric,1) energy_kwh,
               round(sum(cost_vnd)::numeric,0) cost_vnd,
               (SELECT round(max(kw)::numeric,1) FROM peak) peak_kw,
               count(*) FILTER (WHERE comfort_risk = 'high') high_comfort_rows
        FROM w""", b=building_id, now=now)
    return {"window": window, "as_of": str(now), **{k: float(v) if v is not None else None
            for k, v in row.items()}}


def get_zone_timeseries(conn, building_id, zone_key: str, metric: str = "total_power_kw",
                        hours: int = 6) -> dict:
    if metric not in ZONE_METRICS:
        return {"error": f"metric must be one of {sorted(ZONE_METRICS)}"}
    now = _now(conn, building_id)
    rows = fetch_all(conn, f"""
        SELECT timestamp AS ts, {metric} AS value FROM telemetry_zone_15m
        WHERE building_id = :b AND zone_id = (SELECT id FROM zones WHERE entity_key = :zk)
          AND timestamp > :now - interval '{int(hours)} hours' AND timestamp <= :now
        ORDER BY timestamp""", b=building_id, zk=zone_key, now=now)
    return {"zone_key": zone_key, "metric": metric, "hours": hours,
            "points": [{"ts": str(r["ts"]), "value": float(r["value"] or 0)} for r in rows]}


def get_top_consumers(conn, building_id, window: str = "day", limit: int = 5) -> dict:
    iv = WINDOW_INTERVAL.get(window, "1 day")
    now = _now(conn, building_id)
    rows = fetch_all(conn, f"""
        SELECT z.entity_key, z.name, round(sum(t.energy_kwh)::numeric,1) energy_kwh
        FROM telemetry_zone_15m t JOIN zones z ON z.id = t.zone_id
        WHERE t.building_id = :b AND t.timestamp > :now - interval '{iv}'
          AND t.timestamp <= :now
        GROUP BY z.entity_key, z.name ORDER BY energy_kwh DESC LIMIT :lim""",
        b=building_id, now=now, lim=int(limit))
    return {"window": window, "top": [dict(r) | {"energy_kwh": float(r["energy_kwh"])}
            for r in rows]}


def get_alerts(conn, building_id, status: str = "open") -> dict:
    cond = "resolved_at IS NULL" if status == "open" else "resolved_at IS NOT NULL"
    rows = fetch_all(conn, f"""
        SELECT a.alert_type, a.severity, a.message, a.created_at, z.name zone
        FROM alerts a LEFT JOIN zones z ON z.id = a.zone_id
        WHERE a.building_id = :b AND {cond}
        ORDER BY a.created_at DESC LIMIT 20""", b=building_id)
    return {"status": status, "alerts": [dict(r) | {"created_at": str(r["created_at"])}
            for r in rows]}


def list_zones(conn, building_id) -> dict:
    rows = fetch_all(conn, """
        SELECT entity_key, name, room_type, round(area_m2::numeric,1) area_m2
        FROM zones WHERE building_id = :b ORDER BY name""", b=building_id)
    return {"zones": [dict(r) for r in rows]}


# OpenAI/Groq function-calling schemas
TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "get_building_kpi",
        "description": "Total energy (kWh), cost (VND), peak power (kW) and comfort issues for a recent window.",
        "parameters": {"type": "object", "properties": {
            "window": {"type": "string", "enum": ["day", "week", "month"]}}, "required": ["window"]}}},
    {"type": "function", "function": {
        "name": "get_zone_timeseries",
        "description": "Recent time-series of one metric for one zone (by entity_key).",
        "parameters": {"type": "object", "properties": {
            "zone_key": {"type": "string"},
            "metric": {"type": "string", "enum": sorted(ZONE_METRICS)},
            # ["integer","string"]: vài model emit số dạng string -> Groq validate chặt;
            # nhận cả hai rồi int() coerce trong hàm.
            "hours": {"type": ["integer", "string"]}}, "required": ["zone_key", "metric"]}}},
    {"type": "function", "function": {
        "name": "get_top_consumers",
        "description": "Zones using the most energy in a window.",
        "parameters": {"type": "object", "properties": {
            "window": {"type": "string", "enum": ["day", "week", "month"]},
            "limit": {"type": ["integer", "string"]}}, "required": ["window"]}}},
    {"type": "function", "function": {
        "name": "get_alerts",
        "description": "Current building alerts (anomalies, faults).",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "enum": ["open", "resolved"]}}}}},
    {"type": "function", "function": {
        "name": "list_zones",
        "description": "List zones with name, room type, area.",
        "parameters": {"type": "object", "properties": {}}}},
]

_DISPATCH = {"get_building_kpi": get_building_kpi, "get_zone_timeseries": get_zone_timeseries,
             "get_top_consumers": get_top_consumers, "get_alerts": get_alerts,
             "list_zones": list_zones}


def dispatch(name: str, args: dict, conn, building_id) -> dict:
    # KHÔNG nuốt lỗi ở đây: để service bọc savepoint (begin_nested) -> lỗi 1 tool
    # rollback savepoint, không phá transaction đang lưu lịch sử chat.
    fn = _DISPATCH.get(name)
    if fn is None:
        return {"error": f"unknown tool {name}"}
    return fn(conn, building_id, **args)

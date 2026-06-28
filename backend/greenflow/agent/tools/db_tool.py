"""Canonical-DB readers: building, floors, zones, devices, latest state."""

from __future__ import annotations

from ...db import db_conn, fetch_all, fetch_one


def get_building_summary(building_id: str) -> dict:
    with db_conn() as conn:
        b = fetch_one(conn, "SELECT * FROM buildings WHERE id = :b", b=building_id) or {}
        counts = fetch_one(conn, """
            SELECT
              (SELECT count(*) FROM floors WHERE building_id = :b)  AS floor_count,
              (SELECT count(*) FROM zones WHERE building_id = :b)   AS zone_count,
              (SELECT count(*) FROM devices WHERE building_id = :b) AS device_count,
              (SELECT coalesce(sum(area_m2), 0) FROM zones WHERE building_id = :b)
                  AS total_area_m2
        """, b=building_id) or {}
        return {**_clean(b), **_clean(counts)}


def get_floors(building_id: str) -> list[dict]:
    with db_conn() as conn:
        return [_clean(r) for r in fetch_all(conn, """
            SELECT id, floor_index, name, elevation_m FROM floors
            WHERE building_id = :b ORDER BY floor_index
        """, b=building_id)]


def get_zones(building_id: str, floor_id: str | None = None) -> list[dict]:
    with db_conn() as conn:
        sql = """
            SELECT z.id, z.name, z.entity_key, z.room_type, z.area_m2, z.volume_m3,
                   z.comfort_profile, z.floor_id, f.name AS floor_name
            FROM zones z LEFT JOIN floors f ON f.id = z.floor_id
            WHERE z.building_id = :b
        """
        params: dict = {"b": building_id}
        if floor_id:
            sql += " AND z.floor_id = :f"
            params["f"] = floor_id
        return [_clean(r) for r in fetch_all(conn, sql + " ORDER BY z.name", **params)]


def get_devices(building_id: str, zone_id: str | None = None) -> list[dict]:
    with db_conn() as conn:
        sql = """
            SELECT d.id, d.name, d.entity_key, d.device_type, d.device_subtype, d.tag,
                   d.controllable, d.risk_level, d.status, d.nominal_power_kw,
                   d.zone_id, z.name AS zone_name, z.entity_key AS zone_key
            FROM devices d LEFT JOIN zones z ON z.id = d.zone_id
            WHERE d.building_id = :b
        """
        params: dict = {"b": building_id}
        if zone_id:
            sql += " AND d.zone_id = :z"
            params["z"] = zone_id
        return [_clean(r) for r in fetch_all(conn, sql + " ORDER BY d.name", **params)]


def get_cameras(building_id: str, zone_id: str | None = None) -> list[dict]:
    with db_conn() as conn:
        sql = """
            SELECT c.id, c.name, c.video_source, c.privacy_mode, c.zone_id,
                   z.entity_key AS zone_key
            FROM cameras c LEFT JOIN zones z ON z.id = c.zone_id
            WHERE c.building_id = :b
        """
        params: dict = {"b": building_id}
        if zone_id:
            sql += " AND c.zone_id = :z"
            params["z"] = zone_id
        return [_clean(r) for r in fetch_all(conn, sql + " ORDER BY c.name", **params)]


def get_latest_zone_state(building_id: str) -> dict[str, dict]:
    """entity_key -> telemetry row per zone AT the replay 'now' (anchor).

    Telemetry là một năm đã ghi được phát lại; "latest" phải là <= replay anchor
    (vd ngày hè đã ghim), KHÔNG phải max(timestamp)=cuối năm (đông, tải thấp) —
    nếu không agent đọc trạng thái sai mùa, lệch với dashboard."""
    from ...replayclock import anchor
    with db_conn() as conn:
        rows = fetch_all(conn, """
            SELECT DISTINCT ON (t.zone_id) z.entity_key, z.name, z.room_type,
                   t.timestamp, t.occupancy_count, t.occupancy_state,
                   t.occupancy_confidence, t.temperature_c, t.humidity_pct, t.co2_ppm,
                   t.hvac_power_kw, t.lighting_power_kw, t.plug_power_kw,
                   t.total_power_kw, t.setpoint_c, t.comfort_risk, t.peak_risk,
                   t.anomaly_label
            FROM telemetry_zone_15m t JOIN zones z ON z.id = t.zone_id
            WHERE t.building_id = :b AND t.timestamp <= :anchor
            ORDER BY t.zone_id, t.timestamp DESC
        """, b=building_id, anchor=anchor(conn, building_id))
        return {r["entity_key"]: _clean(r) for r in rows}


def get_latest_device_state(building_id: str) -> dict[str, dict]:
    from ...replayclock import anchor
    with db_conn() as conn:
        rows = fetch_all(conn, """
            SELECT DISTINCT ON (t.device_id) d.entity_key, d.name, d.device_subtype,
                   d.controllable, t.timestamp, t.status, t.setpoint_c, t.power_kw,
                   z.entity_key AS zone_key
            FROM telemetry_device_15m t
            JOIN devices d ON d.id = t.device_id
            LEFT JOIN zones z ON z.id = t.zone_id
            WHERE t.building_id = :b AND t.timestamp <= :anchor
            ORDER BY t.device_id, t.timestamp DESC
        """, b=building_id, anchor=anchor(conn, building_id))
        return {r["entity_key"]: _clean(r) for r in rows}


def get_latest_weather(location_name: str | None = None, *, at=None,
                       building_id: str | None = None) -> dict:
    """Return the latest recorded weather at or before the replay timestamp.

    Weather must use the same virtual clock as zone telemetry. Reading the last
    row in the table would show 1 May while a pinned dashboard is on 17 April.
    """
    from ...replayclock import anchor

    with db_conn() as conn:
        replay_at = at or anchor(conn, building_id)
        location_filter = " AND location_name = :location" if location_name else ""
        row = fetch_one(conn, """
            SELECT * FROM weather_15m
            WHERE timestamp <= :replay_at
        """ + location_filter + " ORDER BY timestamp DESC LIMIT 1",
            replay_at=replay_at, location=location_name) or {}
        return _clean(row)


def _clean(row: dict) -> dict:
    """uuid/Decimal/datetime -> JSON-friendly primitives."""
    import datetime
    import decimal
    import uuid as _uuid
    out = {}
    for k, v in row.items():
        if isinstance(v, _uuid.UUID):
            out[k] = str(v)
        elif isinstance(v, decimal.Decimal):
            out[k] = float(v)
        elif isinstance(v, (datetime.datetime, datetime.date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out

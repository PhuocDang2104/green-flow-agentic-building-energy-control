"""Anomaly engine — scans telemetry against anomaly_rules, writes alerts.

Deterministic BATCH rules over a time window (replay clock), not streaming.
Rules live in anomaly_rules (auto-seeded by ensure_rules); alerts go to the
existing alerts table with alert_type = anomaly_rules.id so the UI/chat need no
schema change. Sustained rules group consecutive 30-min rows into episodes
(gaps-and-islands) → one alert per zone per episode, not one per row.

Rules:
  hvac_on_empty                hvac_power_kw > min_kw AND occupancy = 0, sustained
  lighting_after_hours         lighting on outside [work_start,work_end)/weekend
  co2_high                     co2_ppm > co2_max_ppm, sustained
  comfort_violation_sustained  comfort_risk high while occupied, sustained
  sensor_stuck                 a sensor value exact-repeated for >= sustain_min
  device_fault                 device fault_state set, or status=on & power=0

Idempotent: each scan clears prior alerts from these rules for the building, then
re-inserts (full rescan).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from ..db import fetch_all

TZ = timezone(timedelta(hours=7))
STEP_MIN = 30  # telemetry resolution

# Catalog (mirrors db/seed/anomaly_rules.sql); seeded if the table is empty.
DEFAULT_RULES = [
    ("hvac_on_empty", "HVAC running in empty zone", "schedule_deviation",
     {"min_kw": 0.5, "sustain_min": 30}, "warning"),
    ("lighting_after_hours", "Lighting on after hours", "schedule_deviation",
     {"min_kw": 0.2, "work_start": 7, "work_end": 19, "sustain_min": 30}, "warning"),
    ("co2_high", "CO2 above comfort limit", "threshold",
     {"co2_max_ppm": 1000, "sustain_min": 30}, "warning"),
    ("comfort_violation_sustained", "Sustained comfort violation", "threshold",
     {"sustain_min": 45}, "critical"),
    ("sensor_stuck", "Sensor stuck / dropout", "stuck_sensor",
     {"sustain_min": 120}, "info"),
    ("device_fault", "Device fault state", "fault", {}, "critical"),
]


def ensure_rules(conn) -> None:
    if fetch_all(conn, "SELECT 1 FROM anomaly_rules LIMIT 1"):
        return
    for rid, name, rtype, params, sev in DEFAULT_RULES:
        conn.execute(text("""
            INSERT INTO anomaly_rules (id, name, description, rule_type, params, severity)
            VALUES (:id, :n, :n, :t, cast(:p as jsonb), :s)
            ON CONFLICT (id) DO NOTHING
        """), {"id": rid, "n": name, "t": rtype, "p": json.dumps(params), "s": sev})


def _emit(conn, building_id, rule_id, severity, zone_id, device_id, message, when) -> None:
    conn.execute(text("""
        INSERT INTO alerts (building_id, zone_id, device_id, alert_type, severity,
                            message, created_at)
        VALUES (:b, :z, :d, :a, :s, :m, :t)
    """), {"b": building_id, "z": zone_id, "d": device_id, "a": rule_id,
           "s": severity, "m": message, "t": when})


def _zone_episodes(conn, building_id, s, e, cond: str, peak_col: str, sustain_min: int,
                   extra: dict) -> list[dict]:
    """Gaps-and-islands: maximal runs of consecutive rows where `cond` holds,
    kept if run length * step >= sustain_min. `cond`/`peak_col` are code-defined
    (never user input); thresholds are bound params."""
    sql = f"""
        WITH base AS (
            SELECT zone_id, timestamp, ({cond}) AS hit, ({peak_col}) AS pk
            FROM telemetry_zone_15m
            WHERE building_id = :b AND timestamp >= :s AND timestamp <= :e
        ), seq AS (
            SELECT zone_id, timestamp, hit, pk,
                   row_number() OVER (PARTITION BY zone_id ORDER BY timestamp)
                 - row_number() OVER (PARTITION BY zone_id, hit ORDER BY timestamp) AS grp
            FROM base
        ), ep AS (
            SELECT zone_id, min(timestamp) AS started, max(timestamp) AS ended,
                   count(*) AS n, max(pk) AS peak
            FROM seq WHERE hit GROUP BY zone_id, grp
            HAVING count(*) * {STEP_MIN} >= :sustain
        )
        SELECT ep.zone_id, z.name AS zone_name, ep.started, ep.ended, ep.n, ep.peak
        FROM ep JOIN zones z ON z.id = ep.zone_id ORDER BY ep.started
    """
    return fetch_all(conn, sql, b=building_id, s=s, e=e, sustain=sustain_min, **extra)


def _hms(ts) -> str:
    return ts.astimezone(TZ).strftime("%H:%M")


def _scan_sustained(conn, building_id, s, e, rule, cond, peak_col, fmt, extra=None) -> int:
    sustain = int(rule["params"].get("sustain_min", STEP_MIN))
    n = 0
    for ep in _zone_episodes(conn, building_id, s, e, cond, peak_col, sustain, extra or {}):
        mins = ep["n"] * STEP_MIN
        msg = fmt(ep, mins)
        _emit(conn, building_id, rule["id"], rule["severity"], ep["zone_id"], None,
              msg, ep["ended"])
        n += 1
    return n


def _scan_device_fault(conn, building_id, s, e, rule) -> int:
    rows = fetch_all(conn, """
        SELECT DISTINCT ON (t.device_id) t.device_id, t.zone_id, d.name,
               t.fault_state, t.status, t.power_kw, t.timestamp
        FROM telemetry_device_15m t JOIN devices d ON d.id = t.device_id
        WHERE t.building_id = :b AND t.timestamp >= :s AND t.timestamp <= :e
          AND (t.fault_state IS NOT NULL OR (t.status = 'on' AND coalesce(t.power_kw,0) = 0))
        ORDER BY t.device_id, t.timestamp DESC
    """, b=building_id, s=s, e=e)
    for r in rows:
        reason = (f"fault_state={r['fault_state']}" if r["fault_state"]
                  else "on but drawing 0 kW (suspected fault)")
        _emit(conn, building_id, rule["id"], rule["severity"], r["zone_id"], r["device_id"],
              f"{r['name']}: {reason}", r["timestamp"])
    return len(rows)


def _scan_sensor_stuck(conn, building_id, s, e, rule) -> int:
    sustain = int(rule["params"].get("sustain_min", 120))
    rows = fetch_all(conn, f"""
        WITH b AS (
            SELECT zone_id, timestamp, temperature_c,
                   (temperature_c IS NOT DISTINCT FROM
                    lag(temperature_c) OVER (PARTITION BY zone_id ORDER BY timestamp)) AS same
            FROM telemetry_zone_15m
            WHERE building_id = :b AND timestamp >= :s AND timestamp <= :e
        ), seq AS (
            SELECT zone_id, timestamp, same,
                   row_number() OVER (PARTITION BY zone_id ORDER BY timestamp)
                 - row_number() OVER (PARTITION BY zone_id, same ORDER BY timestamp) AS grp
            FROM b
        ), ep AS (
            SELECT zone_id, min(timestamp) AS started, max(timestamp) AS ended, count(*) AS n
            FROM seq WHERE same GROUP BY zone_id, grp HAVING count(*) * {STEP_MIN} >= :sustain
        )
        SELECT ep.zone_id, z.name AS zone_name, ep.started, ep.ended, ep.n
        FROM ep JOIN zones z ON z.id = ep.zone_id ORDER BY ep.started
    """, b=building_id, s=s, e=e, sustain=sustain)
    for ep in rows:
        _emit(conn, building_id, rule["id"], rule["severity"], ep["zone_id"], None,
              f"{ep['zone_name']}: temperature sensor unchanged for "
              f"{ep['n'] * STEP_MIN}min (stuck/dropout)", ep["ended"])
    return len(rows)


def scan_anomalies(conn, building_id, window_start: datetime,
                   window_end: datetime) -> int:
    """Run all enabled rules over [window_start, window_end], (re)insert alerts."""
    ensure_rules(conn)
    rules = {r["id"]: r for r in fetch_all(
        conn, "SELECT id, severity, params FROM anomaly_rules WHERE enabled")}
    if not rules:
        return 0
    # idempotent full rescan: clear prior alerts from these rules for this building
    conn.execute(text("DELETE FROM alerts WHERE building_id = :b AND alert_type = ANY(:ids)"),
                 {"b": building_id, "ids": list(rules)})
    total = 0
    if "hvac_on_empty" in rules:
        r = rules["hvac_on_empty"]
        total += _scan_sustained(
            conn, building_id, window_start, window_end, r,
            "hvac_power_kw > :min_kw AND occupancy_count = 0", "hvac_power_kw",
            lambda ep, m: f"{ep['zone_name']}: HVAC {round(float(ep['peak']),2)} kW with zero "
                          f"occupancy for {m}min ({_hms(ep['started'])}-{_hms(ep['ended'])})",
            {"min_kw": float(r["params"].get("min_kw", 0.5))})
    if "lighting_after_hours" in rules:
        r = rules["lighting_after_hours"]
        p = r["params"]
        cond = ("lighting_power_kw > :min_kw AND ("
                "EXTRACT(hour FROM timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh') < :ws OR "
                "EXTRACT(hour FROM timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh') >= :we OR "
                "EXTRACT(isodow FROM timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh') IN (6,7))")
        total += _scan_sustained(
            conn, building_id, window_start, window_end, r, cond, "lighting_power_kw",
            lambda ep, m: f"{ep['zone_name']}: lighting on after hours "
                          f"({round(float(ep['peak']),2)} kW) for {m}min",
            {"min_kw": float(p.get("min_kw", 0.2)), "ws": int(p.get("work_start", 7)),
             "we": int(p.get("work_end", 19))})
    if "co2_high" in rules:
        r = rules["co2_high"]
        total += _scan_sustained(
            conn, building_id, window_start, window_end, r,
            "co2_ppm > :co2max", "co2_ppm",
            lambda ep, m: f"{ep['zone_name']}: CO2 {int(ep['peak'])} ppm above limit for {m}min",
            {"co2max": float(r["params"].get("co2_max_ppm", 1000))})
    if "comfort_violation_sustained" in rules:
        r = rules["comfort_violation_sustained"]
        total += _scan_sustained(
            conn, building_id, window_start, window_end, r,
            "comfort_risk = 'high' AND occupancy_count > 0", "temperature_c",
            lambda ep, m: f"{ep['zone_name']}: comfort violation {round(float(ep['peak']),1)}°C "
                          f"while occupied for {m}min ({_hms(ep['started'])}-{_hms(ep['ended'])})")
    if "sensor_stuck" in rules:
        total += _scan_sensor_stuck(conn, building_id, window_start, window_end,
                                    rules["sensor_stuck"])
    if "device_fault" in rules:
        total += _scan_device_fault(conn, building_id, window_start, window_end,
                                    rules["device_fault"])
    return total

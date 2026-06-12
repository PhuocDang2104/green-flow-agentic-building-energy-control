"""Time-series readers: zone history, building KPIs, baseline trajectories."""

from __future__ import annotations

from ...db import db_conn, fetch_all, fetch_one
from .db_tool import _clean


def get_zone_history(building_id: str, zone_id: str, hours: int = 24) -> list[dict]:
    with db_conn() as conn:
        return [_clean(r) for r in fetch_all(conn, f"""
            SELECT timestamp, occupancy_count, temperature_c, hvac_power_kw,
                   lighting_power_kw, plug_power_kw, total_power_kw, setpoint_c,
                   comfort_risk, peak_risk
            FROM telemetry_zone_15m
            WHERE building_id = :b AND zone_id = :z
              AND timestamp > now() - interval '{int(hours)} hours'
            ORDER BY timestamp
        """, b=building_id, z=zone_id)]


def get_building_kpis(building_id: str) -> dict:
    """Current KPI card values: total load, occupancy, comfort, actions."""
    with db_conn() as conn:
        latest = fetch_one(conn, """
            SELECT max(timestamp) AS ts FROM telemetry_zone_15m WHERE building_id = :b
        """, b=building_id) or {}
        ts = latest.get("ts")
        if ts is None:
            return {}
        agg = fetch_one(conn, """
            SELECT sum(total_power_kw) AS total_kw,
                   sum(occupancy_count) AS occupancy,
                   avg(occupancy_confidence) AS occ_conf,
                   count(*) FILTER (WHERE comfort_risk = 'watch') AS comfort_watch,
                   count(*) FILTER (WHERE comfort_risk = 'high') AS comfort_high,
                   count(*) FILTER (WHERE peak_risk = 'high') AS peak_high,
                   count(*) FILTER (WHERE anomaly_label IS NOT NULL) AS anomalies
            FROM telemetry_zone_15m WHERE building_id = :b AND timestamp = :ts
        """, b=building_id, ts=ts) or {}
        day_energy = fetch_one(conn, """
            SELECT coalesce(sum(energy_kwh), 0) AS kwh, coalesce(sum(cost_vnd), 0) AS cost
            FROM telemetry_zone_15m
            WHERE building_id = :b AND timestamp::date = (:ts)::date
        """, b=building_id, ts=ts) or {}
        actions = fetch_one(conn, """
            SELECT count(*) FILTER (WHERE status = 'executed') AS executed,
                   count(*) FILTER (WHERE status = 'pending_approval') AS pending
            FROM actions WHERE building_id = :b
              AND requested_at > now() - interval '24 hours'
        """, b=building_id) or {}
        return {"timestamp": ts.isoformat() if ts else None,
                **_clean(agg), **_clean(day_energy), **_clean(actions)}


def get_baseline_summary(building_id: str) -> dict:
    """Latest completed baseline run + totals (parsed from notes JSON)."""
    import json
    with db_conn() as conn:
        run = fetch_one(conn, """
            SELECT id, baseline_label, engine, notes, completed_at
            FROM simulation_runs
            WHERE building_id = :b AND run_kind = 'baseline' AND status = 'completed'
            ORDER BY started_at DESC LIMIT 1
        """, b=building_id)
        if not run:
            return {}
        out = _clean(run)
        notes = out.pop("notes", "") or ""
        if notes.startswith("totals: "):
            try:
                out["totals"] = json.loads(notes[len("totals: "):])
            except json.JSONDecodeError:
                pass
        return out

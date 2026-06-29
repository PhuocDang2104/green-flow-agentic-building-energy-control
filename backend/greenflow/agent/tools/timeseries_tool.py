"""Time-series readers: zone history, building KPIs, baseline trajectories."""

from __future__ import annotations

from ...db import db_conn, fetch_all, fetch_one
from ...replayclock import anchor
from .db_tool import _clean
from ...energy_scope import counted_zone_sql


def get_zone_history(building_id: str, zone_id: str, hours: int = 24) -> list[dict]:
    with db_conn() as conn:
        return [_clean(r) for r in fetch_all(conn, f"""
            SELECT timestamp, occupancy_count, temperature_c, hvac_power_kw,
                   lighting_power_kw, plug_power_kw, total_power_kw, setpoint_c,
                   comfort_risk, peak_risk
            FROM telemetry_zone_15m
            WHERE building_id = :b AND zone_id = :z
              AND timestamp > :anchor - interval '{int(hours)} hours' AND timestamp <= :anchor
            ORDER BY timestamp
        """, b=building_id, z=zone_id, anchor=anchor(conn, building_id))]


def get_today_energy(conn, building_id: str, ts) -> dict:
    """Calendar-day-to-date energy + cost at the replay anchor.

    Single source of truth for "today" energy, shared by the dashboard KPI card
    (get_building_kpis) and the Copilot get_building_kpi tool so both always
    report the same number. QC-01 was caused by two definitions of "today":
    rolling-24h (Copilot, 480 kWh) vs calendar-day (dashboard, 787 kWh).
    """
    row = fetch_one(conn, f"""
        SELECT coalesce(sum(energy_kwh), 0) AS kwh, coalesce(sum(cost_vnd), 0) AS cost
        FROM telemetry_zone_15m t JOIN zones z ON z.id = t.zone_id
        WHERE t.building_id = :b AND {counted_zone_sql('z')}
          AND timestamp::date = (:ts)::date
    """, b=building_id, ts=ts) or {}
    return {"kwh": float(row.get("kwh") or 0), "cost": float(row.get("cost") or 0)}


def get_building_kpis(building_id: str) -> dict:
    """Current KPI card values: total load, occupancy, comfort, actions."""
    with db_conn() as conn:
        ts = anchor(conn, building_id)
        if ts is None:
            return {}
        agg = fetch_one(conn, f"""
            SELECT sum(total_power_kw) AS total_kw,
                   sum(occupancy_count) AS occupancy,
                   avg(occupancy_confidence) AS occ_conf,
                   count(*) FILTER (WHERE comfort_risk = 'watch') AS comfort_watch,
                   count(*) FILTER (WHERE comfort_risk = 'high') AS comfort_high,
                   count(*) FILTER (WHERE peak_risk = 'high') AS peak_high,
                   count(*) FILTER (WHERE anomaly_label IS NOT NULL) AS anomalies
            FROM telemetry_zone_15m t JOIN zones z ON z.id = t.zone_id
            WHERE t.building_id = :b AND {counted_zone_sql('z')} AND timestamp = :ts
        """, b=building_id, ts=ts) or {}
        day_energy = get_today_energy(conn, building_id, ts)
        # Count over ALL open actions (no 24h window) so this KPI matches the
        # Action Queue exactly. QC-03: dashboard showed 21 pending vs queue 38
        # because of a stray `requested_at > now() - interval '24 hours'` here.
        actions = fetch_one(conn, """
            SELECT count(*) FILTER (WHERE status = 'executed') AS executed,
                   count(*) FILTER (WHERE status = 'pending_approval') AS pending
            FROM actions WHERE building_id = :b
        """, b=building_id) or {}
        return {"timestamp": ts.isoformat() if ts else None,
                **_clean(agg),
                "kwh": day_energy["kwh"], "cost": day_energy["cost"],
                **_clean(actions)}


def get_building_health(building_id: str) -> dict:
    """Composite 0-100 building-health score from current state + open faults.

    Four transparent sub-scores (each 0-100), each driven by a real signal at
    the replay anchor, then a weighted overall — an OpenBlue-style "building
    performance" headline that also *pinpoints which dimension is failing*.

      comfort     thermal comfort risk across zones      (weight 0.30)
      air         CO2 / indoor air quality               (weight 0.20)
      energy      peak-demand exposure                   (weight 0.25)
      reliability equipment + sensor fault load          (weight 0.25)

    Penalties are linear in the share of affected zones; only the energy
    dimension is softened (0.6) because peak risk concentrates in the afternoon
    demand window and a single peak hour should not zero it out. Raw counts are
    returned in `detail` so the underlying truth stays transparent.
    """
    with db_conn() as conn:
        ts = anchor(conn, building_id)
        if ts is None:
            return {}
        row = fetch_one(conn, f"""
            SELECT count(*) AS n,
                   count(*) FILTER (WHERE comfort_risk = 'high')  AS comfort_high,
                   count(*) FILTER (WHERE comfort_risk = 'watch') AS comfort_watch,
                   count(*) FILTER (WHERE co2_ppm > 1000)         AS co2_poor,
                   count(*) FILTER (WHERE co2_ppm > 800 AND co2_ppm <= 1000) AS co2_watch,
                   count(*) FILTER (WHERE peak_risk = 'high')     AS peak_high
            FROM telemetry_zone_15m t JOIN zones z ON z.id = t.zone_id
            WHERE t.building_id = :b AND {counted_zone_sql('z')} AND timestamp = :ts
        """, b=building_id, ts=ts) or {}
        faults = fetch_one(conn, """
            SELECT count(*) FILTER (WHERE alert_type = 'device_fault') AS device_faults,
                   count(*) FILTER (WHERE alert_type = 'sensor_stuck') AS sensor_faults
            FROM alerts WHERE building_id = :b AND resolved_at IS NULL
        """, b=building_id) or {}

    n = max(1, int(row.get("n") or 0))
    ch, cw = int(row.get("comfort_high") or 0), int(row.get("comfort_watch") or 0)
    aq_poor, aq_watch = int(row.get("co2_poor") or 0), int(row.get("co2_watch") or 0)
    peak = int(row.get("peak_high") or 0)
    dev_f, sen_f = int(faults.get("device_faults") or 0), int(faults.get("sensor_faults") or 0)

    def score(penalty: float) -> int:
        return max(0, min(100, round(100 * (1 - min(1.0, penalty)))))

    comfort = score((ch + 0.5 * cw) / n)
    air = score((aq_poor + 0.5 * aq_watch) / n)
    energy = score(0.6 * (peak / n))
    reliability = score(dev_f * 0.34 + sen_f * 0.15)

    dims = [
        {"key": "comfort", "label": "Thermal comfort", "score": comfort, "weight": 0.30,
         "detail": f"{ch} high · {cw} watch / {n} zones"},
        {"key": "air", "label": "Air quality", "score": air, "weight": 0.20,
         "detail": f"{aq_poor} >1000ppm · {aq_watch} elevated CO₂"},
        {"key": "energy", "label": "Energy / demand", "score": energy, "weight": 0.25,
         "detail": f"{peak}/{n} zones in peak-demand risk"},
        {"key": "reliability", "label": "Equipment reliability", "score": reliability, "weight": 0.25,
         "detail": f"{dev_f} device · {sen_f} sensor faults"},
    ]
    overall = max(0, min(100, round(sum(d["score"] * d["weight"] for d in dims))))
    if overall >= 85:
        grade, color = "Excellent", "success"
    elif overall >= 70:
        grade, color = "Good", "teal"
    elif overall >= 50:
        grade, color = "Fair", "warning"
    else:
        grade, color = "Poor", "danger"

    return {"timestamp": ts.isoformat(), "score": overall, "grade": grade,
            "color": color, "zones": n, "dimensions": dims}


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

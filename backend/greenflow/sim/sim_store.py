"""Wide simulation-result storage (spine merge, decision #3).

Replaces the EAV `simulation_results` write/read path with the wide
`sim_zone_15m` table. Both writers (simulation_tool, seed_demo) and the reader
(get_run_series) go through here so the storage shape is defined in one place.
The public read shape stays `[{timestamp, value}]`, so the frontend that calls
the simulation endpoints is untouched.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import text

# Metric name (as requested by API/agent) -> wide column. Whitelist: anything
# not here is rejected, so the column name can be interpolated safely.
METRIC_TO_COLUMN: dict[str, str] = {
    "total_power_kw": "total_power_kw",
    "hvac_power_kw": "hvac_power_kw",
    "lighting_power_kw": "lighting_power_kw",
    "plug_power_kw": "plug_power_kw",
    "temperature_c": "temperature_c",
    "zone_temperature_c": "temperature_c",   # legacy EAV alias
    "setpoint_c": "setpoint_c",
    "occupancy_count": "occupancy_count",
}


def write_run_rows(conn, run_id, result, zone_id_by_key: dict[str, str],
                   day_start) -> int:
    """Insert one wide row per (zone, step) for a SimResult. Returns row count.

    zone_id_by_key maps entity_key -> zone uuid. Rows whose zone_key has no uuid
    are skipped (wide PK requires a non-null zone_id).
    """
    rows = []
    for r in result.records:
        zid = zone_id_by_key.get(r.zone_key)
        if zid is None:
            continue
        rows.append({
            "run": run_id,
            "ts": day_start + timedelta(minutes=r.minutes),
            "z": zid,
            "occ": r.occupancy_count,
            "temp": r.temperature_c,
            "sp": r.setpoint_c,
            "hvac": r.hvac_kw,
            "light": r.lighting_kw,
            "plug": r.plug_kw,
            "total": r.total_kw,
            "viol": bool(r.comfort_violated),
        })
    if rows:
        conn.execute(text("""
            INSERT INTO sim_zone_15m (simulation_run_id, zone_id, timestamp,
                occupancy_count, temperature_c, setpoint_c, hvac_power_kw,
                lighting_power_kw, plug_power_kw, total_power_kw, comfort_violated)
            VALUES (:run, :z, :ts, :occ, :temp, :sp, :hvac, :light, :plug, :total, :viol)
            ON CONFLICT (simulation_run_id, zone_id, timestamp) DO NOTHING
        """), rows)
    return len(rows)


def read_run_series(conn, run_id: str, metric: str) -> list[dict]:
    """Building-level series for one run+metric: [{timestamp, value}]."""
    column = METRIC_TO_COLUMN.get(metric)
    if column is None:
        raise ValueError(f"unknown sim metric '{metric}'; "
                         f"allowed: {sorted(METRIC_TO_COLUMN)}")
    rows = conn.execute(text(f"""
        SELECT timestamp, sum({column}) AS value
        FROM sim_zone_15m WHERE simulation_run_id = :r
        GROUP BY timestamp ORDER BY timestamp
    """), {"r": run_id}).mappings().all()
    return [{"timestamp": row["timestamp"], "value": float(row["value"] or 0)}
            for row in rows]

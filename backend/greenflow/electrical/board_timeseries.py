"""Phase 7 — estimated board-level timeseries.

DuckDB streams the gold zone timeseries (the EnergyPlus-simulated energy),
distributes each zone's lights/equipment/HVAC by the Phase-6 allocation weights,
and aggregates to per-board per-timestep demand. Board energy is therefore
*EnergyPlus-simulated energy × inferred allocation* — labelled estimated, never
measured. Current/loading/overload are computed only with real ratings; assumed
power-factor/voltage are flagged and overload stays ``rating_missing`` when no
reliable rated current exists.
"""
from __future__ import annotations

from collections import defaultdict

from . import canonical as C
from . import config as cfg
from . import gold
from .provenance import Confidence, ValueClass
from ..energy_scope import redistribution_enabled
from ..zone_redistribution import SCOPE_CHILD_WEIGHTS_CSV

BOARD_TS = cfg.OUT_ELEC / "board_estimated_timeseries.parquet"
CAT_TS = cfg.OUT_ELEC / "board_load_category_timeseries.parquet"


def _alloc_wide():
    import pyarrow as pa
    wide: dict[tuple, dict] = defaultdict(lambda: {"w_lights": 0.0, "w_equip": 0.0, "w_hvac": 0.0})
    for a in C.read_rows_csv(cfg.OUT_ELEC / "zone_load_to_board_allocation.csv"):
        key = (a["zone_id"], a["board_id"])
        col = {"lights": "w_lights", "equipment": "w_equip", "hvac": "w_hvac"}[a["load_category"]]
        wide[key][col] += float(a["weight"])
    rows = [{"zone_id": z, "board_id": b, **w} for (z, b), w in wide.items()]
    return pa.Table.from_pylist(rows)


def _scope_child_weights_rows() -> list[dict]:
    rows = []
    for row in C.read_rows_csv(cfg.OUT_MAPPING / SCOPE_CHILD_WEIGHTS_CSV):
        try:
            weight = float(row.get("weight") or 0)
        except (TypeError, ValueError):
            weight = 0.0
        if row.get("aggregate_zone_id") and row.get("child_zone_id") and weight > 0:
            rows.append({
                "aggregate_zone_id": row["aggregate_zone_id"],
                "child_zone_id": row["child_zone_id"],
                "weight": weight,
            })
    return rows


def register_scope_child_weights(con) -> int:
    import pyarrow as pa

    rows = _scope_child_weights_rows()
    con.register("scope_child_weights", pa.Table.from_pylist(rows or [{
        "aggregate_zone_id": "",
        "child_zone_id": "",
        "weight": 0.0,
    }]))
    return len(rows)


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _raw_zone_timeseries_projection() -> str:
    source = cfg.parquet_scan(cfg.ZONE_TS)
    if cfg.DATASET_KEY == "elnino_2024_mar_apr":
        return f"""
          SELECT timestep_index,
                 datetime AS timestamp_local,
                 year, month, day, hour, minute,
                 '{cfg.SCENARIO_ID}' AS scenario_id,
                 zone_id,
                 lights_electricity_kw,
                 equipment_electricity_kw,
                 hvac_power_kw AS final_hvac_electricity_kw,
                 lights_electricity_kwh AS lights_electricity_kwh_interval,
                 equipment_electricity_kwh AS equipment_electricity_kwh_interval,
                 hvac_electricity_kwh AS final_hvac_electricity_kwh_interval,
                 target_total_zone_power_kw * {cfg.TIMESTEP_HOURS} AS final_total_zone_electricity_kwh_interval
          FROM read_parquet('{source}', hive_partitioning=true)
        """
    return f"SELECT * FROM read_parquet('{source}', hive_partitioning=true)"


def _zone_timeseries_projection() -> str:
    raw = _raw_zone_timeseries_projection()
    if not redistribution_enabled() or not _scope_child_weights_rows():
        return raw
    return f"""
      WITH raw_zone_ts AS ({raw}),
           aggregate_ids AS (
             SELECT DISTINCT aggregate_zone_id FROM scope_child_weights WHERE weight > 0
           ),
           kept AS (
             SELECT * FROM raw_zone_ts
             WHERE zone_id NOT IN (SELECT aggregate_zone_id FROM aggregate_ids)
           ),
           redistributed AS (
             SELECT z.timestep_index,
                    z.timestamp_local,
                    z.year, z.month, z.day, z.hour, z.minute,
                    z.scenario_id,
                    w.child_zone_id AS zone_id,
                    z.lights_electricity_kw * w.weight AS lights_electricity_kw,
                    z.equipment_electricity_kw * w.weight AS equipment_electricity_kw,
                    z.final_hvac_electricity_kw * w.weight AS final_hvac_electricity_kw,
                    z.lights_electricity_kwh_interval * w.weight
                      AS lights_electricity_kwh_interval,
                    z.equipment_electricity_kwh_interval * w.weight
                      AS equipment_electricity_kwh_interval,
                    z.final_hvac_electricity_kwh_interval * w.weight
                      AS final_hvac_electricity_kwh_interval,
                    z.final_total_zone_electricity_kwh_interval * w.weight
                      AS final_total_zone_electricity_kwh_interval
             FROM raw_zone_ts z
             JOIN scope_child_weights w ON z.zone_id = w.aggregate_zone_id
             WHERE w.weight > 0
           )
      SELECT * FROM kept
      UNION ALL
      SELECT * FROM redistributed
    """


def run() -> dict[str, int]:
    cfg.ensure_dirs()
    con = gold.duckdb_con()
    con.execute("PRAGMA memory_limit='4GB'")
    con.execute(f"SET temp_directory='{(cfg.OUT_ELEC).as_posix()}/_duck_tmp'")
    con.register("alloc_wide", _alloc_wide())
    register_scope_child_weights(con)

    contrib = f"""
      SELECT a.board_id, z.timestep_index, z.timestamp_local,
             z.year, z.month, z.day, z.hour, z.minute,
             z.lights_electricity_kw * a.w_lights AS lkw,
             z.equipment_electricity_kw * a.w_equip AS ekw,
             z.final_hvac_electricity_kw * a.w_hvac AS hkw,
             z.lights_electricity_kwh_interval * a.w_lights AS lkwh,
             z.equipment_electricity_kwh_interval * a.w_equip AS ekwh,
             z.final_hvac_electricity_kwh_interval * a.w_hvac AS hkwh
      FROM ({_zone_timeseries_projection()}) z
      JOIN alloc_wide a ON z.zone_id = a.zone_id
      WHERE z.scenario_id = '{cfg.SCENARIO_ID}'
    """

    con.execute(f"""
      COPY (
        SELECT board_id, timestep_index,
               any_value(timestamp_local) AS timestamp_local,
               any_value(year) AS year, any_value(month) AS month, any_value(day) AS day,
               any_value(hour) AS hour, any_value(minute) AS minute,
               sum(lkw) AS board_lights_kw, sum(ekw) AS board_equipment_kw,
               sum(hkw) AS board_hvac_kw, sum(lkw + ekw + hkw) AS board_total_kw,
               sum(lkwh) AS board_lights_kwh_interval, sum(ekwh) AS board_equipment_kwh_interval,
               sum(hkwh) AS board_hvac_kwh_interval,
               sum(lkwh + ekwh + hkwh) AS board_total_kwh_interval
        FROM ({contrib}) GROUP BY board_id, timestep_index
      ) TO '{BOARD_TS.as_posix()}' (FORMAT PARQUET)
    """)
    n_rows = con.execute(f"SELECT count(*) FROM read_parquet('{BOARD_TS.as_posix()}')").fetchone()[0]

    # long per-category timeseries
    con.execute(f"""
      COPY (
        SELECT board_id, timestep_index, any_value(timestamp_local) AS timestamp_local,
               any_value(month) AS month, 'lights' AS category, sum(lkw) AS kw, sum(lkwh) AS kwh_interval
        FROM ({contrib}) GROUP BY board_id, timestep_index
        UNION ALL
        SELECT board_id, timestep_index, any_value(timestamp_local), any_value(month),
               'equipment', sum(ekw), sum(ekwh) FROM ({contrib}) GROUP BY board_id, timestep_index
        UNION ALL
        SELECT board_id, timestep_index, any_value(timestamp_local), any_value(month),
               'hvac', sum(hkw), sum(hkwh) FROM ({contrib}) GROUP BY board_id, timestep_index
      ) TO '{CAT_TS.as_posix()}' (FORMAT PARQUET)
    """)

    # ---- annual + monthly + peak summaries ----
    annual = con.execute(f"""
      SELECT board_id,
             sum(board_lights_kwh_interval) AS lights_kwh,
             sum(board_equipment_kwh_interval) AS equipment_kwh,
             sum(board_hvac_kwh_interval) AS hvac_kwh,
             sum(board_total_kwh_interval) AS total_kwh,
             max(board_total_kw) AS peak_total_kw,
             arg_max(timestamp_local, board_total_kw) AS peak_timestamp,
             max(board_lights_kw) AS peak_lights_kw,
             max(board_equipment_kw) AS peak_equipment_kw,
             max(board_hvac_kw) AS peak_hvac_kw
      FROM read_parquet('{BOARD_TS.as_posix()}') GROUP BY board_id
    """).fetch_arrow_table().to_pylist()
    monthly = con.execute(f"""
      SELECT board_id, month,
             sum(board_lights_kwh_interval) AS lights_kwh,
             sum(board_equipment_kwh_interval) AS equipment_kwh,
             sum(board_hvac_kwh_interval) AS hvac_kwh,
             sum(board_total_kwh_interval) AS total_kwh,
             max(board_total_kw) AS peak_total_kw
      FROM read_parquet('{BOARD_TS.as_posix()}') GROUP BY board_id, month ORDER BY board_id, month
    """).fetch_arrow_table().to_pylist()
    con.close()

    boards = {b["board_id"]: b for b in C.read_rows_csv(cfg.OUT_ELEC / "electrical_boards.csv")}
    ann_rows, peak_rows, phase_rows = [], [], []
    for a in annual:
        b = boards.get(a["board_id"], {})
        volt = _f(b.get("voltage_v"))
        phase = _f(b.get("phase_count"))
        pf = _f(b.get("power_factor"))
        rated = _f(b.get("rated_current_a"))
        # voltage / pf with assumed fallbacks (flagged)
        v_source = "ifc_derived"
        if not volt:
            volt = cfg.DEFAULT_VOLTAGE_3P if (phase == 3) else cfg.DEFAULT_VOLTAGE_1P
            v_source = "assumed_default"
        pf_source = "ifc_derived"
        if not pf or pf <= 0:
            pf = cfg.DEFAULT_POWER_FACTOR
            pf_source = "assumed_default"
        peak_kw = _f(a["peak_total_kw"]) or 0.0
        denom = (cfg.SQRT3 * volt * pf) if (phase == 3) else (volt * pf)
        cur = (peak_kw * 1000.0 / denom) if denom else None
        if rated and rated > 0:
            loading = round(cur / rated * 100.0, 1) if cur else None
            status = ("overload" if loading and loading >= cfg.LOADING_OVERLOAD_PCT
                      else "warning" if loading and loading >= cfg.LOADING_WARN_PCT else "normal")
        else:
            loading, status = None, "rating_missing"
        if a["board_id"] == cfg.UNMAPPED_BOARD_ID:
            cur, loading, status = None, None, "unmapped"
        ann_rows.append({
            "board_id": a["board_id"], "name": b.get("name"), "device_tag": b.get("device_tag"),
            "floor_id": b.get("floor_id"), "system_code": b.get("system_code"),
            "voltage_v": volt, "voltage_source": v_source, "phase_count": phase,
            "power_factor": round(pf, 3), "pf_source": pf_source,
            "rated_current_a": rated,
            "lights_kwh": round(_f(a["lights_kwh"]) or 0, 2),
            "equipment_kwh": round(_f(a["equipment_kwh"]) or 0, 2),
            "hvac_kwh": round(_f(a["hvac_kwh"]) or 0, 2),
            "total_kwh": round(_f(a["total_kwh"]) or 0, 2),
            "peak_total_kw": round(peak_kw, 3), "peak_timestamp": a["peak_timestamp"],
            "estimated_peak_current_a": round(cur, 1) if cur else None,
            "current_method": ("3ph P/(sqrt3*V*PF)" if phase == 3 else "1ph P/(V*PF)"),
            "loading_pct": loading, "overload_status": status,
            "value_class": ValueClass.SPATIALLY_INFERRED,
            "notes": "estimated: EnergyPlus-simulated zone energy x inferred allocation"
                     + ("; current uses assumed PF/voltage" if (pf_source == "assumed_default"
                        or v_source == "assumed_default") else ""),
        })
        peak_rows.append({
            "board_id": a["board_id"], "device_tag": b.get("device_tag"), "floor_id": b.get("floor_id"),
            "peak_total_kw": round(peak_kw, 3), "peak_timestamp": a["peak_timestamp"],
            "peak_lights_kw": round(_f(a["peak_lights_kw"]) or 0, 3),
            "peak_equipment_kw": round(_f(a["peak_equipment_kw"]) or 0, 3),
            "peak_hvac_kw": round(_f(a["peak_hvac_kw"]) or 0, 3),
            "overload_status": status, "value_class": ValueClass.SPATIALLY_INFERRED,
        })
        phase_rows.append({
            "board_id": a["board_id"], "phase_count": phase,
            "phase_imbalance_pct": None, "status": "not_available",
            "reason": "no per-phase load allocation available (single-phase circuit "
                      "assignment not modelled)", "confidence": Confidence.MANUAL_REVIEW,
        })

    ann_rows.sort(key=lambda r: -(r["peak_total_kw"] or 0))
    C.write_rows_csv(cfg.OUT_ELEC / "board_annual_summary.csv", ann_rows)
    C.write_rows_csv(cfg.OUT_ELEC / "board_monthly_summary.csv",
                     [{"board_id": m["board_id"], "month": m["month"],
                       "lights_kwh": round(_f(m["lights_kwh"]) or 0, 2),
                       "equipment_kwh": round(_f(m["equipment_kwh"]) or 0, 2),
                       "hvac_kwh": round(_f(m["hvac_kwh"]) or 0, 2),
                       "total_kwh": round(_f(m["total_kwh"]) or 0, 2),
                       "peak_total_kw": round(_f(m["peak_total_kw"]) or 0, 3)} for m in monthly])
    C.write_rows_csv(cfg.OUT_ELEC / "board_peak_demand_summary.csv", peak_rows)
    C.write_rows_csv(cfg.OUT_ELEC / "phase_balance_summary.csv", phase_rows)
    return {"board_timestep_rows": int(n_rows), "boards_summarised": len(ann_rows),
            "monthly_rows": len(monthly)}


if __name__ == "__main__":
    print(run())

"""Validate the true-building El Nino data spine.

Hard checks run against ``data/final_elnino``. Postgres/electrical checks are
reported when available, so the script is usable both before and after loading
the app database.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import duckdb  # noqa: E402

from greenflow.datasets import active_dataset  # noqa: E402

EXPECTED = {
    "zones": 308,
    "timesteps": 2928,
    "zone_rows": 901824,
    "march_kwh": 157737.0,
    "april_kwh": 192847.0,
    "apr25_kwh": 9040.2,
}


def _duckdb_source(table: str) -> tuple[duckdb.DuckDBPyConnection, str, str]:
    ds = active_dataset()
    if ds.duckdb_path.exists():
        return duckdb.connect(str(ds.duckdb_path), read_only=True), table, str(ds.duckdb_path)
    parquet = ds.parquet_root / f"{table}.parquet"
    if not parquet.exists():
        raise SystemExit(
            f"missing DuckDB and parquet fallback. Tried: {ds.duckdb_path} and {parquet}"
        )
    return duckdb.connect(), f"read_parquet('{parquet.as_posix()}')", str(parquet)


def _ok_close(actual: float | None, expected: float, tol: float) -> bool:
    return actual is not None and abs(float(actual) - expected) <= tol


def _duckdb_checks(duckdb_path: Path) -> dict[str, Any]:
    con, source, source_label = _duckdb_source("final_ai_training_timeseries")
    row = con.execute("""
        SELECT count(DISTINCT zone_id) AS zones,
               count(DISTINCT datetime) AS timesteps,
               count(*) AS zone_rows,
               min(datetime) AS min_ts,
               max(datetime) AS max_ts
        FROM {source}
    """.format(source=source)).fetchone()
    totals = con.execute("""
        SELECT
          sum(CASE WHEN datetime >= TIMESTAMP '2024-03-01'
                    AND datetime < TIMESTAMP '2024-04-01'
                   THEN target_total_zone_power_kw * 0.5 ELSE 0 END) AS march_kwh,
          sum(CASE WHEN datetime >= TIMESTAMP '2024-04-01'
                    AND datetime < TIMESTAMP '2024-05-01'
                   THEN target_total_zone_power_kw * 0.5 ELSE 0 END) AS april_kwh,
          sum(CASE WHEN datetime >= TIMESTAMP '2024-04-25'
                    AND datetime < TIMESTAMP '2024-04-26'
                   THEN target_total_zone_power_kw * 0.5 ELSE 0 END) AS apr25_kwh,
          sum(lights_electricity_kwh) AS lights_kwh,
          sum(equipment_electricity_kwh) AS equipment_kwh,
          sum(hvac_electricity_kwh) AS hvac_kwh,
          sum(target_total_zone_power_kw * 0.5) AS total_kwh
        FROM {source}
    """.format(source=source)).fetchone()
    keys = ("zones", "timesteps", "zone_rows", "min_ts", "max_ts")
    out = dict(zip(keys, row, strict=True))
    out["source"] = source_label
    out.update(dict(zip((
        "march_kwh", "april_kwh", "apr25_kwh", "lights_kwh",
        "equipment_kwh", "hvac_kwh", "total_kwh",
    ), totals, strict=True)))
    out["checks"] = {
        "zones": out["zones"] == EXPECTED["zones"],
        "timesteps": out["timesteps"] == EXPECTED["timesteps"],
        "zone_rows": out["zone_rows"] == EXPECTED["zone_rows"],
        "march_kwh": _ok_close(out["march_kwh"], EXPECTED["march_kwh"], 1.0),
        "april_kwh": _ok_close(out["april_kwh"], EXPECTED["april_kwh"], 1.0),
        "apr25_kwh": _ok_close(out["apr25_kwh"], EXPECTED["apr25_kwh"], 1.0),
    }
    return out


def _postgres_checks(building_id: str, scenario_id: str) -> dict[str, Any]:
    try:
        from greenflow.db import db_conn, fetch_all

        with db_conn() as conn:
            zones = fetch_all(conn, """
                SELECT count(*) AS zones
                FROM zones WHERE building_id = :b
            """, b=building_id)[0]["zones"]
            tel = fetch_all(conn, """
                SELECT count(*) AS rows, count(DISTINCT zone_id) AS zones,
                       min(timestamp) AS min_ts, max(timestamp) AS max_ts,
                       sum(energy_kwh) AS total_kwh
                FROM telemetry_zone_15m
                WHERE building_id = :b
                  AND (CAST(:scn AS text) IS NULL
                       OR scenario_id = CAST(:scn AS text)
                       OR scenario_id IS NULL)
            """, b=building_id, scn=scenario_id)[0]
            weather = fetch_all(conn, """
                SELECT count(*) AS rows, min(timestamp) AS min_ts, max(timestamp) AS max_ts
                FROM weather_15m
            """)[0]
        return {
            "available": True,
            "zones_table_count": zones,
            "telemetry": dict(tel),
            "weather": dict(weather),
            "checks": {
                "zones_table_count": int(zones) >= EXPECTED["zones"],
                "telemetry_rows": int(tel["rows"] or 0) == EXPECTED["zone_rows"],
                "telemetry_zones": int(tel["zones"] or 0) == EXPECTED["zones"],
                "weather_rows": int(weather["rows"] or 0) == EXPECTED["timesteps"],
            },
        }
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": repr(exc)[:240]}


def _electrical_checks(path: Path, scenario_id: str) -> dict[str, Any]:
    parquet = path / "board_estimated_timeseries.parquet"
    if not parquet.exists():
        return {"available": False, "path": str(parquet), "error": "artifact missing"}
    try:
        con = duckdb.connect()
        cols = {r[0] for r in con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{parquet.as_posix()}')"
        ).fetchall()}
        time_col = "timestamp_local" if "timestamp_local" in cols else "timestamp"
        scenario_expr = "count(DISTINCT scenario_id)" if "scenario_id" in cols else "NULL"
        if "total_kwh" in cols:
            total_expr = "sum(total_kwh)"
        elif "board_total_kwh_interval" in cols:
            total_expr = "sum(board_total_kwh_interval)"
        else:
            total_expr = "NULL"
        row = con.execute(f"""
            SELECT count(*) AS rows,
                   min({time_col}) AS min_ts,
                   max({time_col}) AS max_ts,
                   {scenario_expr} AS scenario_count,
                   {total_expr} AS total_kwh
            FROM read_parquet('{parquet.as_posix()}')
        """).fetchone()
        return {
            "available": True,
            "path": str(parquet),
            "rows": row[0],
            "min_ts": row[1],
            "max_ts": row[2],
            "scenario_count": row[3],
            "total_kwh": row[4],
            "scenario_id": scenario_id,
        }
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "path": str(parquet), "error": repr(exc)[:240]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--building-id", default="b0000000-0000-0000-0000-000000000001")
    ap.add_argument("--check-postgres", action="store_true")
    ap.add_argument("--require-postgres", action="store_true")
    args = ap.parse_args()

    ds = active_dataset()
    check_pg = args.check_postgres or args.require_postgres
    out = {
        "dataset": ds.to_metadata(),
        "expected": EXPECTED,
        "duckdb": _duckdb_checks(ds.duckdb_path),
        "postgres": (_postgres_checks(args.building_id, ds.scenario_id) if check_pg
                     else {"available": False, "skipped": True}),
        "electrical": _electrical_checks(ds.electrical_out, ds.scenario_id),
    }
    print(json.dumps(out, indent=2, default=str))

    hard = out["duckdb"]["checks"]
    ok = all(hard.values())
    if args.require_postgres:
        ok = ok and out["postgres"].get("available") and all(
            out["postgres"].get("checks", {}).values())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

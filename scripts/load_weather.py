"""Seed weather_15m from a dataset DuckDB's final_weather_timeseries.

The campaign what-if (and any weather-aware feature) needs REAL outdoor conditions
— without this, the surrogate gets flat default weather and setpoint deltas stop
differentiating. Pairs with load_real_data.py (telemetry); run after it.

  docker exec -e DUCKDB_PATH=/data/elnino_2024/...duckdb greenflow-api \
    python /app/scripts/load_weather.py
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import duckdb  # noqa: E402
from sqlalchemy import text  # noqa: E402

from greenflow.datasets import active_dataset  # noqa: E402
from greenflow.db import db_conn  # noqa: E402

TZ = timezone(timedelta(hours=7))
LOC = os.environ.get("WEATHER_LOCATION", "Hanoi")
DATASET = active_dataset()
DUCKDB_PATH = os.environ.get("DUCKDB_PATH") or str(DATASET.duckdb_path)


def _duckdb_source(table: str) -> tuple[duckdb.DuckDBPyConnection, str, str]:
    path = Path(DUCKDB_PATH)
    if path.exists():
        return duckdb.connect(str(path), read_only=True), table, str(path)
    parquet = DATASET.parquet_root / f"{table}.parquet"
    if not parquet.exists():
        raise SystemExit(
            f"missing DuckDB and parquet fallback. Tried: {path} and {parquet}"
        )
    return duckdb.connect(), f"read_parquet('{parquet.as_posix()}')", str(parquet)


def main() -> None:
    con, source, source_label = _duckdb_source("final_weather_timeseries")
    print(f"reading weather source: {source_label}")
    rows = con.execute("""
        SELECT datetime, outdoor_temp_c, outdoor_rh_pct, wind_speed_m_s,
               COALESCE(total_sky_cover_tenths, 4) * 10 AS cloud_pct,
               COALESCE(liquid_precip_depth_mm, 0) AS precip,
               global_horizontal_radiation_w_m2 AS solar
        FROM {source} ORDER BY datetime""".format(source=source)).fetchall()
    recs = [{"ts": r[0].replace(tzinfo=TZ), "loc": LOC, "t": r[1], "h": r[2],
             "w": r[3], "c": r[4], "p": r[5], "s": r[6]} for r in rows]
    ins = text("""
        INSERT INTO weather_15m (timestamp, location_name, outdoor_temp_c, humidity_pct,
            wind_speed_mps, cloud_cover_pct, precipitation_mm, solar_w_m2, forecast_horizon_min)
        VALUES (:ts, :loc, :t, :h, :w, :c, :p, :s, 0)
        ON CONFLICT (timestamp, location_name) DO UPDATE SET
            outdoor_temp_c=EXCLUDED.outdoor_temp_c, humidity_pct=EXCLUDED.humidity_pct,
            wind_speed_mps=EXCLUDED.wind_speed_mps, cloud_cover_pct=EXCLUDED.cloud_cover_pct,
            precipitation_mm=EXCLUDED.precipitation_mm, solar_w_m2=EXCLUDED.solar_w_m2""")
    with db_conn() as conn:
        for i in range(0, len(recs), 1000):
            conn.execute(ins, recs[i:i + 1000])
    print(f"weather_15m: upserted {len(recs)} rows for {LOC} "
          f"({recs[0]['ts']} .. {recs[-1]['ts']})")


if __name__ == "__main__":
    main()

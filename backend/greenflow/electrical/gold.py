"""Access to the existing EnergyPlus postprocessed ('gold') dataset under
data/final — the simulated energy source of truth. We never re-simulate; we read
the patched zone/meter Parquet via pyarrow (dimensions) and DuckDB (timeseries).
"""
from __future__ import annotations

from functools import lru_cache

import pyarrow.compute as pc
import pyarrow.dataset as ds

from . import config as cfg

ZONE_GLOB = cfg.parquet_scan(cfg.ZONE_TS)
METER_GLOB = cfg.parquet_scan(cfg.METER_TS)


@lru_cache(maxsize=1)
def zone_dimensions() -> list[dict]:
    """One row per zone: zone_id, eplus_zone_name, area/volume/usage (static dims)."""
    if cfg.DATASET_KEY == "elnino_2024_mar_apr":
        con = duckdb_con()
        rows = con.execute(f"""
            SELECT zone_id,
                   any_value(eplus_zone_name) AS eplus_zone_name,
                   any_value(room_type) AS usage_type,
                   any_value(area_m2_final) AS area_m2,
                   any_value(volume_m3_final) AS volume_m3,
                   any_value(height_m_final) AS ceiling_height_m
            FROM read_parquet('{ZONE_GLOB}', hive_partitioning=true)
            GROUP BY zone_id
            ORDER BY zone_id
        """).fetch_arrow_table().to_pylist()
        con.close()
        return [{
            "zone_id": r["zone_id"],
            "eplus_zone_name": r["eplus_zone_name"],
            "classification": r["usage_type"] or "unknown",
            "conditioned_flag": True,
            "usage_type": r["usage_type"] or "unknown",
            "area_m2": r["area_m2"],
            "volume_m3": r["volume_m3"],
            "ceiling_height_m": r["ceiling_height_m"],
        } for r in rows]
    d = ds.dataset(str(cfg.ZONE_TS), format="parquet", partitioning="hive")
    cols = ["zone_id", "eplus_zone_name", "classification", "conditioned_flag",
            "usage_type", "area_m2", "volume_m3", "ceiling_height_m"]
    tbl = d.to_table(columns=cols, filter=(ds.field("month") == 1))
    agg = tbl.group_by("zone_id").aggregate(
        [(c, "min") for c in cols if c != "zone_id"])
    rows = []
    for r in agg.to_pylist():
        rows.append({"zone_id": r["zone_id"],
                     "eplus_zone_name": r["eplus_zone_name_min"],
                     "classification": r["classification_min"],
                     "conditioned_flag": r["conditioned_flag_min"],
                     "usage_type": r["usage_type_min"],
                     "area_m2": r["area_m2_min"],
                     "volume_m3": r["volume_m3_min"],
                     "ceiling_height_m": r["ceiling_height_m_min"]})
    return rows


@lru_cache(maxsize=1)
def zone_eplus_map() -> dict[str, str]:
    return {r["zone_id"]: r["eplus_zone_name"] for r in zone_dimensions()}


def duckdb_con():
    import duckdb
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    return con


def meter_names() -> list[str]:
    if cfg.DATASET_KEY == "elnino_2024_mar_apr":
        return ["Electricity:Facility", "Electricity:HVAC",
                "InteriorLights:Electricity", "InteriorEquipment:Electricity"]
    d = ds.dataset(str(cfg.METER_TS), format="parquet", partitioning="hive")
    tbl = d.to_table(columns=["meter_name"], filter=(ds.field("month") == 1))
    return pc.unique(tbl["meter_name"]).to_pylist()

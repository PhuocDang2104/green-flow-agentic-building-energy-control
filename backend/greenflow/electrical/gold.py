"""Access to the existing EnergyPlus postprocessed ('gold') dataset under
data/final — the simulated energy source of truth. We never re-simulate; we read
the patched zone/meter Parquet via pyarrow (dimensions) and DuckDB (timeseries).
"""
from __future__ import annotations

from functools import lru_cache

import pyarrow.compute as pc
import pyarrow.dataset as ds

from . import config as cfg

ZONE_GLOB = str(cfg.ZONE_TS / "**" / "*.parquet")
METER_GLOB = str(cfg.METER_TS / "**" / "*.parquet")


@lru_cache(maxsize=1)
def zone_dimensions() -> list[dict]:
    """One row per zone: zone_id, eplus_zone_name, area/volume/usage (static dims)."""
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
    d = ds.dataset(str(cfg.METER_TS), format="parquet", partitioning="hive")
    tbl = d.to_table(columns=["meter_name"], filter=(ds.field("month") == 1))
    return pc.unique(tbl["meter_name"]).to_pylist()

"""Feed the demo building's 5 archetype zones with REAL EnergyPlus data.

Spine merge — decision #1 (data follows spine) reconciled with decision #5
(frontend/3D untouched). See docs/spine/CONFLICT_RESOLUTION.md.

The frontend renders 5 archetype zones (zone_storey0_open_office/office/meeting/
amenity/circulation) of the demo building b0000000-...-001. The real pipeline
produced 188 zones of verified EnergyPlus telemetry, and every real zone maps
to exactly one of those 5 archetypes (tools/idf/out/archetype_zone_map.json:
office 114 · meeting 29 · circulation 20 · amenity 14 · open_office 11).

This script aggregates the 188 real zones up to the 5 archetype zones per
15-min step (sum power/energy/cost/occupancy; area-agnostic mean for
temperature/CO2/setpoint) and REPLACES the synthetic telemetry_zone_15m of the
demo building. The frontend is untouched yet now shows real-derived numbers.

Run after `make seed` (which creates the demo building + its 5 zones):
  python scripts/load_real_into_demo.py \
      --zone-state "../tools/datagen/out/zone_state_15m.parquet" \
      --archetype-map "../tools/idf/out/archetype_zone_map.json"
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

from greenflow.db import db_conn, fetch_all  # noqa: E402

BUILDING_ID = uuid.UUID("b0000000-0000-0000-0000-000000000001")

ARCHETYPE_TO_KEY = {
    "open_office": "zone_storey0_open_office",
    "office": "zone_storey0_office",
    "meeting": "zone_storey0_meeting",
    "amenity": "zone_storey0_amenity",
    "circulation": "zone_storey0_circulation",
}


def comfort_risk(violation_min: float) -> str:
    if violation_min >= 5:
        return "high"
    if violation_min > 0:
        return "watch"
    return "normal"


def occupancy_state(count: float) -> str:
    if count < 0.5:
        return "empty"
    if count < 5:
        return "low"
    if count < 20:
        return "normal"
    return "high"


def aggregate(zone_state_path: Path, archetype_map_path: Path) -> pd.DataFrame:
    arche = {z["zone_id"]: z["archetype"]
             for z in json.loads(archetype_map_path.read_text())["zones"]}
    df = pd.read_parquet(zone_state_path, columns=[
        "timestamp", "zone_id", "occupancy_count", "temperature_c", "humidity_pct",
        "co2_ppm", "hvac_power_kw", "lighting_power_kw", "plug_power_kw",
        "total_power_kw", "energy_kwh", "cost_vnd", "cooling_setpoint_c",
        "comfort_violation_min"])
    df["demo_key"] = df["zone_id"].map(arche).map(ARCHETYPE_TO_KEY)
    df = df.dropna(subset=["demo_key"])

    g = df.groupby(["demo_key", "timestamp"]).agg(
        occupancy_count=("occupancy_count", "sum"),
        temperature_c=("temperature_c", "mean"),
        humidity_pct=("humidity_pct", "mean"),
        co2_ppm=("co2_ppm", "mean"),
        hvac_power_kw=("hvac_power_kw", "sum"),
        lighting_power_kw=("lighting_power_kw", "sum"),
        plug_power_kw=("plug_power_kw", "sum"),
        total_power_kw=("total_power_kw", "sum"),
        energy_kwh=("energy_kwh", "sum"),
        cost_vnd=("cost_vnd", "sum"),
        setpoint_c=("cooling_setpoint_c", "mean"),
        comfort_violation_min=("comfort_violation_min", "sum"),
    ).reset_index()

    # naive local (Asia/Ho_Chi_Minh) -> tz-aware so the timestamptz is correct
    # regardless of DB session timezone.
    g["timestamp"] = g["timestamp"].dt.tz_localize("Asia/Ho_Chi_Minh")
    g["comfort_risk"] = g["comfort_violation_min"].map(comfort_risk)
    g["occupancy_state"] = g["occupancy_count"].map(occupancy_state)
    return g


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--zone-state", required=True)
    ap.add_argument("--archetype-map", required=True)
    args = ap.parse_args()

    agg = aggregate(Path(args.zone_state), Path(args.archetype_map))
    print(f"aggregated {len(agg):,} rows over {agg['demo_key'].nunique()} demo zones, "
          f"{agg['timestamp'].nunique():,} steps")

    with db_conn() as conn:
        zone_uuid = {z["entity_key"]: z["id"] for z in fetch_all(
            conn, "SELECT id, entity_key FROM zones WHERE building_id = :b",
            b=BUILDING_ID)}
        floor_row = fetch_all(
            conn, "SELECT id FROM floors WHERE building_id = :b ORDER BY floor_index LIMIT 1",
            b=BUILDING_ID)
        floor_id = floor_row[0]["id"] if floor_row else None
        missing = set(ARCHETYPE_TO_KEY.values()) - set(zone_uuid)
        if missing:
            print(f"ERROR: demo zones not seeded: {missing}. Run `make seed` first.",
                  file=sys.stderr)
            return 1

        print("replacing synthetic telemetry_zone_15m for demo building ...")
        conn.execute(text("DELETE FROM telemetry_zone_15m WHERE building_id = :b"),
                     {"b": BUILDING_ID})

        rows = [{
            "ts": r.timestamp.to_pydatetime(), "b": BUILDING_ID, "f": floor_id,
            "z": zone_uuid[r.demo_key],
            "occ": int(r.occupancy_count), "occ_state": r.occupancy_state,
            "occ_conf": 0.95, "temp": float(r.temperature_c),
            "hum": float(r.humidity_pct), "co2": float(r.co2_ppm),
            "hvac": float(r.hvac_power_kw), "light": float(r.lighting_power_kw),
            "plug": float(r.plug_power_kw), "total": float(r.total_power_kw),
            "energy": float(r.energy_kwh), "cost": float(r.cost_vnd),
            "sp": float(r.setpoint_c), "comfort": r.comfort_risk,
        } for r in agg.itertuples(index=False)]

        sql = text("""
            INSERT INTO telemetry_zone_15m (timestamp, building_id, floor_id, zone_id,
                occupancy_count, occupancy_state, occupancy_confidence, temperature_c,
                humidity_pct, co2_ppm, hvac_power_kw, lighting_power_kw, plug_power_kw,
                total_power_kw, energy_kwh, cost_vnd, setpoint_c, comfort_risk,
                scenario_id)
            VALUES (:ts, :b, :f, :z, :occ, :occ_state, :occ_conf, :temp, :hum, :co2,
                    :hvac, :light, :plug, :total, :energy, :cost, :sp, :comfort,
                    'real_eplus')
            ON CONFLICT (timestamp, zone_id) DO UPDATE SET
                total_power_kw = EXCLUDED.total_power_kw,
                hvac_power_kw = EXCLUDED.hvac_power_kw,
                temperature_c = EXCLUDED.temperature_c""")
        for i in range(0, len(rows), 5000):
            conn.execute(sql, rows[i:i + 5000])
        print(f"inserted {len(rows):,} real-derived rows into demo building.")
    print("done. Dashboard now shows real EnergyPlus-derived numbers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

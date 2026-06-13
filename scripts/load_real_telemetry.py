"""Load the real EnergyPlus telemetry (188 BIM zones, Jun-Aug 2025) into Postgres.

Spine merge: brings the verified real-data pipeline output (VinHack workspace
`tools/datagen` + `tools/idf`, physics = EnergyPlus 26.1, EUI 179 kWh/m2/yr,
surrogate R2 0.95) into this repo's schema — as a SECOND building, so the
synthetic archetype demo building (b000...001) is untouched.

Key mapping (schema here is uuid-keyed): every IFC GUID gets a deterministic
uuid5; the GUID itself is preserved in entity_key + raw_ifc_guid, so the 3D
viewer / agent can still resolve by GUID.

Parquet contract: docs/spine/PARQUET_SCHEMA.md. Timestamps in the parquet are
naive local (Asia/Ho_Chi_Minh) — the COPY session pins that timezone; loading
with a UTC session would shift every peak by 7 hours with no error raised.

Limitation (docs/spine/DECISIONS_AND_CRITIQUE.md D3): telemetry PK here is
(timestamp, zone_id) without a run dimension, so only ONE run tag can occupy a
window; reloading with the same --run-tag wipes and replaces it.

Usage:
  python scripts/load_real_telemetry.py \
      --bim-map "../Dataset/BIM/extracted/office_concrete/zone_equipment_map.json" \
      --data-dir "../tools/datagen/out" [--run-tag baseline] [--with-devices]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import pyarrow.parquet as pq  # noqa: E402
from sqlalchemy import text  # noqa: E402

from greenflow.db import db_conn, get_engine  # noqa: E402

NS = uuid.uuid5(uuid.NAMESPACE_URL, "greenflow/office_concrete")
BUILDING_ID = uuid.uuid5(NS, "building")

CATEGORY_MAP = {
    "open office": "open_office", "office": "office", "meeting": "meeting_room",
    "negotiation": "meeting_room", "conference": "meeting_room", "lobby": "lobby",
    "hall": "hallway", "corridor": "hallway", "staircase": "staircase",
    "wc": "restroom", "toilet": "restroom", "server": "server_room",
    "electrical": "electrical_room", "technical": "utility_room",
    "storage": "storage", "kitchen": "amenity", "pantry": "amenity",
}
CRITICAL = {"server_room", "electrical_room", "utility_room"}
CONTROLLABLE_TYPES = {"IfcAirTerminal", "IfcLightFixture", "IfcSpaceHeater",
                      "IfcUnitaryEquipment"}


def guid_uuid(guid: str) -> uuid.UUID:
    return uuid.uuid5(NS, guid)


def room_category(room_type: str | None) -> str:
    rt = (room_type or "").lower()
    for key, slug in CATEGORY_MAP.items():
        if key in rt:
            return slug
    return "other"


def load_entities(conn, bim_map: dict) -> dict[str, tuple[uuid.UUID, uuid.UUID | None]]:
    """Insert building/floors/zones/devices; return zone GUID -> (zone_uuid, floor_uuid)."""
    conn.execute(text(
        """INSERT INTO buildings (id, name, location_name, timezone, building_type, source_dataset)
           VALUES (:id, 'GreenFlow Office (BIM, 188 zones, E+ real)',
                   'Hanoi, VN (EPW Noi Bai)', 'Asia/Ho_Chi_Minh', 'office',
                   'ARK_NordicLCA_Office_Concrete')
           ON CONFLICT (id) DO NOTHING"""), {"id": BUILDING_ID})

    zones = bim_map["zones"]
    floor_ids: dict[str, uuid.UUID] = {}
    for z in zones:
        fg = z.get("floor_guid")
        if fg and fg not in floor_ids:
            floor_ids[fg] = guid_uuid(fg)
            conn.execute(text(
                """INSERT INTO floors (id, building_id, floor_index, name, raw_ifc_guid)
                   VALUES (:id, :b, :idx, :name, :guid)
                   ON CONFLICT (id) DO NOTHING"""),
                {"id": floor_ids[fg], "b": BUILDING_ID, "idx": len(floor_ids) - 1,
                 "name": z.get("floor_name") or fg, "guid": fg})

    zone_map: dict[str, tuple[uuid.UUID, uuid.UUID | None]] = {}
    n_dev = 0
    for z in zones:
        zguid = z["zone_id"]
        zid = guid_uuid(zguid)
        fid = floor_ids.get(z.get("floor_guid"))
        category = room_category(z.get("room_type"))
        zone_map[zguid] = (zid, fid)
        conn.execute(text(
            """INSERT INTO zones (id, building_id, floor_id, name, entity_key, room_type,
                                  area_m2, comfort_profile, risk_level, raw_ifc_guid,
                                  source_space_name)
               VALUES (:id, :b, :f, :name, :key, :rt, :area, 'office_standard',
                       :risk, :guid, :src)
               ON CONFLICT (id) DO UPDATE SET room_type = EXCLUDED.room_type,
                                              area_m2 = EXCLUDED.area_m2"""),
            {"id": zid, "b": BUILDING_ID, "f": fid, "name": z.get("zone_name") or zguid,
             "key": zguid, "rt": category, "area": z.get("area_m2"),
             "risk": "critical" if category in CRITICAL else "normal",
             "guid": zguid, "src": z.get("zone_name")})
        for d in z.get("devices", []):
            dguid = d["guid"]
            dtype = d.get("type", "Unknown")
            scope = d.get("scope", "zone")
            conn.execute(text(
                """INSERT INTO devices (id, building_id, floor_id, zone_id, device_type,
                                        device_subtype, name, entity_key, controllable,
                                        risk_level, raw_ifc_guid)
                   VALUES (:id, :b, :f, :z, :t, :st, :name, :key, :ctrl, 'normal', :guid)
                   ON CONFLICT (id) DO NOTHING"""),
                {"id": guid_uuid(dguid), "b": BUILDING_ID, "f": fid, "z": zid,
                 "t": dtype, "st": scope, "name": d.get("name") or dguid, "key": dguid,
                 "ctrl": dtype in CONTROLLABLE_TYPES and scope == "zone"
                         and category not in CRITICAL,
                 "guid": dguid})
            n_dev += 1
    print(f"entities: {len(zones)} zones, {n_dev} devices, {len(floor_ids)} floors")
    return zone_map


ZONE_COLS = ("timestamp, building_id, floor_id, zone_id, occupancy_count, occupancy_state, "
             "occupancy_confidence, temperature_c, humidity_pct, co2_ppm, hvac_power_kw, "
             "lighting_power_kw, plug_power_kw, total_power_kw, energy_kwh, cost_vnd, "
             "setpoint_c, comfort_risk, scenario_id")

DEVICE_COLS = ("timestamp, building_id, zone_id, device_id, device_type, status, "
               "setpoint_c, power_kw, energy_kwh, runtime_minutes, fault_state, "
               "command_source, scenario_id")


def copy_zone_state(raw_conn, path: Path, zone_map: dict, run_tag: str) -> None:
    t0, total = time.time(), 0
    with raw_conn.cursor() as cur:
        cur.execute("SET timezone = 'Asia/Ho_Chi_Minh'")
        cur.execute(
            "DELETE FROM telemetry_zone_15m WHERE building_id = %s AND scenario_id = %s",
            (BUILDING_ID, run_tag))
        with cur.copy(f"COPY telemetry_zone_15m ({ZONE_COLS}) FROM STDIN") as cp:
            for batch in pq.ParquetFile(path).iter_batches(batch_size=200_000):
                rows = batch.to_pylist()
                for r in rows:
                    ids = zone_map.get(r["zone_id"])
                    if not ids:
                        continue
                    zid, fid = ids
                    cp.write_row((
                        r["timestamp"], BUILDING_ID, fid, zid,
                        r["occupancy_count"], r["occupancy_state"], 0.95,
                        r["temperature_c"], r["humidity_pct"], r["co2_ppm"],
                        r["hvac_power_kw"], r["lighting_power_kw"], r["plug_power_kw"],
                        r["total_power_kw"], r["energy_kwh"], r["cost_vnd"],
                        r["cooling_setpoint_c"], r["comfort_risk"], run_tag,
                    ))
                total += len(rows)
                print(f"  zone_state: {total:,} rows", end="\r", flush=True)
    raw_conn.commit()
    print(f"\ntelemetry_zone_15m: {total:,} rows in {time.time() - t0:.0f}s")


def copy_device_state(raw_conn, path: Path, zone_map: dict, run_tag: str) -> None:
    t0, total = time.time(), 0
    with raw_conn.cursor() as cur:
        cur.execute("SET timezone = 'Asia/Ho_Chi_Minh'")
        cur.execute(
            "DELETE FROM telemetry_device_15m WHERE building_id = %s AND scenario_id = %s",
            (BUILDING_ID, run_tag))
        with cur.copy(f"COPY telemetry_device_15m ({DEVICE_COLS}) FROM STDIN") as cp:
            for batch in pq.ParquetFile(path).iter_batches(batch_size=200_000):
                for r in batch.to_pylist():
                    ids = zone_map.get(r["zone_id"])
                    cp.write_row((
                        r["timestamp"], BUILDING_ID, ids[0] if ids else None,
                        guid_uuid(r["device_id"]), r["device_type"],
                        r["status"] or "unknown", r["setpoint_c"], r["power_kw"],
                        r["energy_kwh"], int(r["runtime_minutes"] or 0),
                        r["fault_state"], r["command_source"], run_tag,
                    ))
                total += batch.num_rows
                print(f"  device_state: {total:,} rows", end="\r", flush=True)
    raw_conn.commit()
    print(f"\ntelemetry_device_15m: {total:,} rows in {time.time() - t0:.0f}s")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bim-map", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--run-tag", default="baseline")
    ap.add_argument("--with-devices", action="store_true",
                    help="also load ~11M device rows (slow)")
    args = ap.parse_args()

    bim_map = json.loads(Path(args.bim_map).read_text())
    data_dir = Path(args.data_dir)

    with db_conn() as conn:
        zone_map = load_entities(conn, bim_map)

    raw = get_engine().raw_connection()
    try:
        copy_zone_state(raw, data_dir / "zone_state_15m.parquet", zone_map, args.run_tag)
        if args.with_devices:
            copy_device_state(raw, data_dir / "device_state_15m.parquet",
                              zone_map, args.run_tag)
    finally:
        raw.close()
    print(f"done. building_id={BUILDING_ID}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

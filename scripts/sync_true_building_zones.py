"""Upsert all 308 El Nino zones into the demo building.

This prepares Postgres before ``scripts/load_real_data.py`` runs in
true-building mode. Zone keys keep the app convention:

    DuckDB zone_id: tz_abc
    App entity_key: zone_abc

The script is idempotent and does not delete existing zones.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import duckdb  # noqa: E402
from sqlalchemy import text  # noqa: E402

from greenflow.datasets import active_dataset  # noqa: E402
from greenflow.db import db_conn, fetch_all  # noqa: E402

BUILDING_ID = uuid.UUID("b0000000-0000-0000-0000-000000000001")
NS = uuid.uuid5(uuid.NAMESPACE_URL, "greenflow/true-building/elnino-2024")


def stable_uuid(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(NS, f"{kind}:{key}")


def entity_key(zone_id: str) -> str:
    return "zone_" + zone_id[len("tz_"):] if zone_id.startswith("tz_") else zone_id


def floor_index(floor_key: str | None) -> int:
    if not floor_key:
        return 0
    digits = "".join(ch for ch in floor_key if ch.isdigit())
    return int(digits) if digits else 0


def read_zone_metadata(duckdb_path: Path) -> list[dict]:
    ds = active_dataset()
    if duckdb_path.exists():
        con = duckdb.connect(str(duckdb_path), read_only=True)
        source = "final_zone_metadata"
        source_label = str(duckdb_path)
    else:
        parquet = ds.parquet_root / "final_zone_metadata.parquet"
        if not parquet.exists():
            raise SystemExit(
                f"missing DuckDB and parquet fallback. Tried: {duckdb_path} and {parquet}"
            )
        con = duckdb.connect()
        source = f"read_parquet('{parquet.as_posix()}')"
        source_label = str(parquet)
    print(f"reading zone metadata: {source_label}")
    rows = con.execute("""
        SELECT zone_id, eplus_zone_name, room_id, room_name, floor_id, room_type,
               area_m2_final, volume_m3_final, height_m_final
        FROM {source}
        ORDER BY zone_id
    """.format(source=source)).fetchall()
    cols = [
        "zone_id", "eplus_zone_name", "room_id", "room_name", "floor_id", "room_type",
        "area_m2_final", "volume_m3_final", "height_m_final",
    ]
    return [dict(zip(cols, r, strict=True)) for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--duckdb-path", default=None)
    args = ap.parse_args()

    ds = active_dataset()
    duckdb_path = Path(args.duckdb_path) if args.duckdb_path else ds.duckdb_path
    zones = read_zone_metadata(duckdb_path)
    if not zones:
        raise SystemExit(f"no zones found in {duckdb_path}")

    floors = sorted({z["floor_id"] or "floor_unknown" for z in zones})
    floor_ids: dict[str, uuid.UUID] = {}

    with db_conn() as conn:
        conn.execute(text("""
            INSERT INTO buildings (id, name, location_name, timezone, building_type, source_dataset)
            VALUES (:id, 'GreenFlow', 'Hanoi / VinUniversity Area',
                    'Asia/Ho_Chi_Minh', 'office', :source)
            ON CONFLICT (id) DO UPDATE SET
                source_dataset = EXCLUDED.source_dataset,
                timezone = EXCLUDED.timezone
        """), {"id": BUILDING_ID, "source": ds.key})

        for floor_key in floors:
            row = conn.execute(text("""
                INSERT INTO floors (id, building_id, floor_index, name, raw_ifc_guid)
                VALUES (:id, :b, :idx, :name, :guid)
                ON CONFLICT (building_id, floor_index) DO UPDATE SET
                    name = EXCLUDED.name,
                    raw_ifc_guid = EXCLUDED.raw_ifc_guid
                RETURNING id
            """), {
                "id": stable_uuid("floor", floor_key),
                "b": BUILDING_ID,
                "idx": floor_index(floor_key),
                "name": floor_key,
                "guid": floor_key,
            }).fetchone()
            floor_ids[floor_key] = row[0]

        zone_records = []
        for z in zones:
            key = entity_key(z["zone_id"])
            name = z["room_name"] or z["eplus_zone_name"] or key
            zone_records.append({
                "id": stable_uuid("zone", key),
                "b": BUILDING_ID,
                "f": floor_ids.get(z["floor_id"] or "floor_unknown"),
                "name": name,
                "key": key,
                "rt": z["room_type"] or "unknown",
                "area": z["area_m2_final"],
                "volume": z["volume_m3_final"],
                "guid": z["zone_id"],
                "src": z["eplus_zone_name"] or z["room_id"] or z["zone_id"],
            })

        upsert_zone = text("""
            INSERT INTO zones (id, building_id, floor_id, name, entity_key, room_type,
                               area_m2, volume_m3, comfort_profile, risk_level,
                               raw_ifc_guid, source_space_name)
            VALUES (:id, :b, :f, :name, :key, :rt, :area, :volume,
                    'office_standard', 'normal', :guid, :src)
            ON CONFLICT (building_id, entity_key) DO UPDATE SET
                floor_id = EXCLUDED.floor_id,
                name = EXCLUDED.name,
                room_type = EXCLUDED.room_type,
                area_m2 = EXCLUDED.area_m2,
                volume_m3 = EXCLUDED.volume_m3,
                raw_ifc_guid = EXCLUDED.raw_ifc_guid,
                source_space_name = EXCLUDED.source_space_name
        """)
        for i in range(0, len(zone_records), 1000):
            conn.execute(upsert_zone, zone_records[i:i + 1000])

        counts = fetch_all(conn, """
            SELECT count(*) AS zones, count(DISTINCT floor_id) AS floors
            FROM zones WHERE building_id = :b
        """, b=BUILDING_ID)[0]

    print(
        f"synced true-building zones: source={duckdb_path} "
        f"upserted={len(zone_records)} db_zones={counts['zones']} floors={counts['floors']}"
    )
    if len(zone_records) != ds.expected_zones:
        raise SystemExit(f"expected {ds.expected_zones} zones, got {len(zone_records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

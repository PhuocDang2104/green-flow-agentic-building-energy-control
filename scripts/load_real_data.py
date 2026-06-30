"""Load REAL EnergyPlus + Open-Meteo telemetry (DuckDB) into Postgres.

Thay telemetry tổng hợp (seed_demo) bằng dữ liệu THẬT: mô phỏng EnergyPlus đủ năm
2025 @30-phút, thời tiết Open-Meteo thật. Toà nhà giống hệt repo — 14 zone demo
khớp 1:1 (`zone_<x>` ↔ `tz_<x>`), nên chỉ cần đổi prefix.

Giữ nguyên độ phân giải **30 phút** (KHÔNG upsample 15-phút: nội suy = data giả,
không feature nào cần — peak/cost/forecast/replay đều đúng ở 30-phút). Bảng
`telemetry_zone_15m` giữ tên (chỉ là quy ước), chứa 30-phút.

Trường THẬT từ E+: total/hvac/lights/equipment kW + kWh_interval, nhiệt độ, RH,
cooling setpoint. Trường SUY RA (không có trong E+, đánh dấu rõ): occupancy
(profile giờ × diện tích × mật độ theo room_type), co2_ppm (ước lượng theo
occupancy), comfort_risk (temp>26.5 khi có người), peak_risk (tải toà nhà so với
đỉnh năm), cost_vnd (biểu giá EVN).

Chạy trong container có DuckDB + reach Postgres (db:5432):
  docker compose run --rm -v "<Dataset>:/data:ro" -v "$PWD/scripts:/app/scripts" \
    api bash -lc "pip install -q duckdb && python /app/scripts/load_real_data.py"
"""
from __future__ import annotations

import os
import sys
import uuid
import csv
import math
from collections import defaultdict
from datetime import timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import duckdb  # noqa: E402
from sqlalchemy import text  # noqa: E402

from greenflow.datasets import active_dataset  # noqa: E402
from greenflow.db import db_conn, fetch_all  # noqa: E402
from greenflow.energy_scope import AGGREGATE, effective_counts_toward_energy, telemetry_scope_mode  # noqa: E402
from greenflow.electrical import config as electrical_cfg  # noqa: E402
from greenflow.zone_redistribution import SCOPE_CHILD_WEIGHTS_CSV  # noqa: E402

BUILDING_ID = uuid.UUID("b0000000-0000-0000-0000-000000000001")
TZ = timezone(timedelta(hours=7))  # Hà Nội; timestamp trong data là local naive
DATASET_SCHEMA = os.environ.get("DATASET_SCHEMA", "elnino2024")  # v2025 | elnino2024
DATASET = active_dataset()

# Crosswalk cột theo schema dataset. Gói El Niño Mar-Apr 2024 đổi tên cột và có
# occupancy THẬT (zone_people_occupant_count) thay vì ước lượng. ts dùng cột
# TIMESTAMP `datetime` (cột `timestamp` ở gói mới là VARCHAR).
COLMAPS = {
    "v2025": {
        "ts": "timestamp", "occ": None,
        "temp": "zone_air_temp_c", "rh": "zone_rh_pct", "sp": "cooling_setpoint_c",
        "hvac": "final_hvac_electricity_kw", "light": "lights_electricity_kw",
        "equip": "equipment_electricity_kw",
        "total": "final_total_zone_electricity_kw",
        "kwh": "final_total_zone_electricity_kwh_interval",
        "default_path": "/data/Dat_data/greenflow_final_mode_b_plus_openmeteo_2025_30min_patched-001.duckdb",
        "scenario_id": "openmeteo_2025_30min_baseline",
    },
    "elnino2024": {
        "ts": "datetime", "occ": "zone_people_occupant_count",
        "temp": "zone_air_temperature_c", "rh": "zone_air_relative_humidity_pct",
        "sp": "cooling_setpoint_c",
        "hvac": "hvac_power_kw", "light": "lights_electricity_kw",
        "equip": "equipment_electricity_kw",
        # zone_total_electricity_kw = lights+equip CHỈ (không HVAC). Tổng ĐÚNG gồm
        # HVAC là target_total_zone_power_kw; kwh suy ra = tổng × 0.5h (mốc 30').
        "total": "target_total_zone_power_kw",
        "kwh": "target_total_zone_power_kw * 0.5",
        "default_path": "/data/elnino_2024/greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd_SELF_CONTAINED.duckdb",
        "scenario_id": "elnino_2024_mar_apr_baseline",
    },
}
CM = COLMAPS[DATASET_SCHEMA]
DUCKDB_PATH = (os.environ.get("DUCKDB_PATH") or
               (str(DATASET.duckdb_path) if DATASET_SCHEMA == "elnino2024"
                else CM["default_path"]))
SCENARIO_ID = CM["scenario_id"]
LOAD_ALL_ZONES = os.environ.get(
    "GREENFLOW_LOAD_ALL_ZONES",
    "1" if DATASET_SCHEMA == "elnino2024" else "0",
).lower() in {"1", "true", "yes", "on"}
COMFORT_LIMIT_C = 26.5  # khớp synthetic_baseline

# người/m2 theo room_type (ước lượng để suy occupancy — E+ không xuất số người)
DENSITY = {"open_office": 0.10, "office": 0.08, "meeting_room": 0.40, "lobby": 0.05,
           "circulation": 0.02, "amenity": 0.06, "auditorium": 0.5}
DEFAULT_DENSITY = 0.08
# fraction occupancy theo giờ làm việc; ĐÊM = 0 (văn phòng trống, không có "ma"
# lúc 3h sáng) -> comfort/hvac episode chỉ trong giờ có người, duration thực tế.
HOUR_OCC = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: .05, 7: .3, 8: .7,
            9: .95, 10: 1.0, 11: 1.0, 12: .6, 13: .9, 14: 1.0, 15: 1.0, 16: .95,
            17: .6, 18: .25, 19: .08, 20: 0, 21: 0, 22: 0, 23: 0}


def occ_fraction(dt) -> float:
    if dt.weekday() >= 5:      # cuối tuần văn phòng đóng
        return 0.0
    return HOUR_OCC.get(dt.hour, 0.0)


def tariff_vnd(hour: float) -> int:
    """EVN business tariff (khớp sim/kpi.py)."""
    if hour < 4 or hour >= 22:
        return 1184
    if (9.5 <= hour < 11.5) or (17 <= hour < 20):
        return 3314
    return 1839


def _entity_key(zone_id: str) -> str:
    return "zone_" + zone_id[len("tz_"):] if str(zone_id).startswith("tz_") else str(zone_id)


def _read_child_weights() -> dict[str, list[tuple[str, float]]]:
    path = electrical_cfg.OUT_MAPPING / SCOPE_CHILD_WEIGHTS_CSV
    if not path.exists():
        print(f"redistribution weights not found: {path}")
        return {}
    out: dict[str, list[tuple[str, float]]] = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                weight = float(row.get("weight") or 0)
            except (TypeError, ValueError):
                weight = 0.0
            if weight <= 0:
                continue
            out[_entity_key(row["aggregate_zone_id"])].append(
                (_entity_key(row["child_zone_id"]), weight)
            )
    return dict(out)


def _occ_allocations(total_occ: int, weights: list[tuple[str, float]]) -> dict[str, int]:
    raw = [(child, max(0.0, total_occ * weight)) for child, weight in weights]
    floors = {child: int(math.floor(value)) for child, value in raw}
    residual = int(total_occ) - sum(floors.values())
    if residual > 0:
        ranked = sorted(raw, key=lambda x: (x[1] - math.floor(x[1])), reverse=True)
        for child, _value in ranked[:residual]:
            floors[child] += 1
    return floors


def _refresh_occupancy_fields(record: dict, zone_meta: dict) -> None:
    room = zone_meta["room_type"]
    dens = DENSITY.get(room, DEFAULT_DENSITY)
    cap = max(1.0, float(zone_meta["area_m2"] or 0) * dens)
    ratio = min(1.0, float(record["occ"] or 0) / cap)
    record["st"] = ("empty" if record["occ"] == 0 else "low" if ratio < 0.25
                    else "medium" if ratio < 0.7 else "high")
    record["co2"] = round(420 + 600 * ratio)
    record["comfort"] = ("high" if record["occ"] > 0 and record["temp"] > COMFORT_LIMIT_C
                         else "watch" if record["temp"] > COMFORT_LIMIT_C - 1 else "normal")


def _redistribute_records(records: list[dict], zmap: dict[str, dict]) -> list[dict]:
    mode = telemetry_scope_mode()
    if mode not in {"exclude_aggregate", "redistribute"}:
        return records

    def is_aggregate(record: dict) -> bool:
        return str(zmap[record["key"]].get("energy_scope") or "") == AGGREGATE

    if mode == "exclude_aggregate":
        out = [record for record in records if not is_aggregate(record)]
        print(f"telemetry scope exclude_aggregate: {len(records):,} -> {len(out):,} rows")
        return out

    child_weights = _read_child_weights()
    if not child_weights:
        print("telemetry scope redistribute requested but no weights found; keeping raw records")
        return records

    out_by_key: dict[tuple, dict] = {}
    aggregate_records: list[dict] = []
    for record in records:
        if is_aggregate(record):
            aggregate_records.append(record)
            continue
        out_by_key[(record["ts"], record["key"])] = dict(record)

    unmapped = set()
    for aggregate in aggregate_records:
        weights = child_weights.get(aggregate["key"])
        if not weights:
            unmapped.add(aggregate["key"])
            out_by_key[(aggregate["ts"], aggregate["key"])] = dict(aggregate)
            continue
        occ_by_child = _occ_allocations(int(aggregate["occ"] or 0), weights)
        for child_key, weight in weights:
            child_meta = zmap.get(child_key)
            if not child_meta:
                continue
            key = (aggregate["ts"], child_key)
            if key not in out_by_key:
                out_by_key[key] = {
                    **aggregate,
                    "key": child_key,
                    "f": child_meta["floor_id"],
                    "z": child_meta["id"],
                    "occ": 0,
                }
            target = out_by_key[key]
            target["occ"] = int(target.get("occ") or 0) + occ_by_child.get(child_key, 0)
            for field in ("hvac", "light", "plug", "total", "kwh", "cost"):
                target[field] = round(float(target.get(field) or 0) + float(aggregate[field] or 0) * weight, 5)
            _refresh_occupancy_fields(target, child_meta)

    out = list(out_by_key.values())
    print(
        "telemetry scope redistribute: "
        f"{len(records):,} raw rows -> {len(out):,} effective rows; "
        f"aggregate rows redistributed={len(aggregate_records) - len(unmapped):,}; "
        f"unmapped aggregates={len(unmapped)}"
    )
    return out


REPO_ENTITY_KEYS = [
    "zone_3jzuKaCoj7duM8YUpx6IdZ", "zone_3H2AkZFqzChQTN2UOTW_7V",
    "zone_1xBFBS5N18MfdblikYnUBD", "zone_0Q4MSUQx531vKL_w06AgFJ",
    "zone_3xtnrBUgHBCwRh_xfyB8zE", "zone_36Blhdds16DOgkiAVsP5oS",
    "zone_0tWM7C8ybBZQ4c5DL1_lzg", "zone_2EmhthfYTF_hx0gAAa2KtI",
    "zone_3xtnrBUgHBCwRh_xfyB626", "zone_0tWM7C8ybBZQ4c5DL1_lwj",
    "zone_3xtnrBUgHBCwRh_xfyB4IZ", "zone_3xtnrBUgHBCwRh_xfyB1VR",
    "zone_1xBFBS5N18MfdblikYnUB5", "zone_0Q4MSUQx531vKL_w06AgFH",
]


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
    # 1) zones trong Postgres: entity_key -> (uuid, floor_id, room_type, area)
    with db_conn() as conn:
        zrows = fetch_all(conn, """
            SELECT entity_key, id, floor_id, room_type, area_m2,
                   energy_scope, counts_toward_energy
            FROM zones WHERE building_id = :b""", b=BUILDING_ID)
    zmap = {r["entity_key"]: r for r in zrows}

    # 2) kéo timeseries thật từ DuckDB hoặc parquet fallback.
    con, source, source_label = _duckdb_source("final_ai_training_timeseries")
    print(f"reading source: {source_label}")
    if LOAD_ALL_ZONES:
        tz_ids = [r[0] for r in con.execute("""
            SELECT DISTINCT zone_id
            FROM {source}
            ORDER BY zone_id
        """.format(source=source)).fetchall()]
        tz_to_key = {
            zid: ("zone_" + zid[len("tz_"):]) if str(zid).startswith("tz_") else str(zid)
            for zid in tz_ids
        }
        mode = "all-zones"
    else:
        tz_to_key = {"tz_" + k[len("zone_"):]: k for k in REPO_ENTITY_KEYS}
        tz_ids = list(tz_to_key)
        mode = "repo-14"
    target_keys = list(tz_to_key.values())
    missing = [k for k in target_keys if k not in zmap]
    if missing:
        sample = ", ".join(missing[:8])
        suffix = "..." if len(missing) > 8 else ""
        raise SystemExit(
            f"zones missing in Postgres: {len(missing)} ({sample}{suffix}). "
            "Run scripts/sync_true_building_zones.py before true-building load."
        )
    ph = ",".join(["?"] * len(tz_ids))
    sel = ", ".join([CM["ts"], "zone_id", CM["temp"], CM["rh"], CM["sp"],
                     CM["hvac"], CM["light"], CM["equip"], CM["total"], CM["kwh"]]
                    + ([CM["occ"]] if CM["occ"] else []))
    rows = con.execute(f"""
        SELECT {sel}
        FROM {source}
        WHERE zone_id IN ({ph})
        ORDER BY {CM['ts']}""", tz_ids).fetchall()
    print(f"pulled {len(rows):,} rows ({len(tz_ids)} zones, mode={mode})")

    # 3) tải toà nhà theo timestamp -> ngưỡng peak_risk (so với đỉnh năm)
    bt: dict = {}
    for r in rows:
        key = tz_to_key[r[1]]
        if effective_counts_toward_energy(zmap[key]["counts_toward_energy"]):
            bt[r[0]] = bt.get(r[0], 0.0) + (r[8] or 0.0)
    bpeak = max(bt.values()) if bt else 1.0
    counted_count = sum(
        effective_counts_toward_energy(zmap[k]["counts_toward_energy"])
        for k in target_keys
    )
    print(f"building peak ({counted_count}/{len(tz_ids)} counted zones): {bpeak:.1f} kW")

    # 4) transform -> tuples
    records = []
    for r in rows:
        ts, zid, temp, rh, sp, hvac, light, equip, total, kwh = r[:10]
        real_occ = r[10] if CM["occ"] else None
        key = tz_to_key[zid]
        z = zmap[key]
        dt = ts.replace(tzinfo=TZ)
        room = z["room_type"]
        dens = DENSITY.get(room, DEFAULT_DENSITY)
        cap = max(1.0, float(z["area_m2"] or 0) * dens)
        # occupancy: số THẬT nếu dataset có (elnino2024), else ước lượng theo lịch
        occ = (round(float(real_occ or 0)) if real_occ is not None
               else round(float(z["area_m2"] or 0) * dens * occ_fraction(dt)))
        ratio = min(1.0, occ / cap)
        state = ("empty" if occ == 0 else "low" if ratio < 0.25
                 else "medium" if ratio < 0.7 else "high")
        co2 = round(420 + 600 * ratio)                       # ước lượng
        comfort = ("high" if occ > 0 and temp > COMFORT_LIMIT_C
                   else "watch" if temp > COMFORT_LIMIT_C - 1 else "normal")
        b = bt[ts]
        peak = ("high" if b >= 0.85 * bpeak else "watch" if b >= 0.6 * bpeak else "normal")
        hour = dt.hour + dt.minute / 60.0
        cost = round(float(kwh or 0) * tariff_vnd(hour))
        records.append({
            "ts": dt, "b": BUILDING_ID, "f": z["floor_id"], "z": z["id"],
            "key": key,
            "occ": occ, "st": state, "conf": 0.85, "temp": round(temp, 2),
            "rh": round(rh, 1), "co2": co2, "hvac": round(hvac, 4),
            "light": round(light, 4), "plug": round(equip, 4), "total": round(total, 4),
            "kwh": round(float(kwh or 0), 5), "cost": cost, "sp": round(sp, 2),
            "comfort": comfort, "peak": peak, "scn": SCENARIO_ID})

    # 5) ghi vào Postgres (thay telemetry cũ)
    records = _redistribute_records(records, zmap)

    ins = text("""
        INSERT INTO telemetry_zone_15m
          (timestamp, building_id, floor_id, zone_id, occupancy_count, occupancy_state,
           occupancy_confidence, temperature_c, humidity_pct, co2_ppm, hvac_power_kw,
           lighting_power_kw, plug_power_kw, total_power_kw, energy_kwh, cost_vnd,
           setpoint_c, comfort_risk, peak_risk, anomaly_label, scenario_id)
        VALUES (:ts,:b,:f,:z,:occ,:st,:conf,:temp,:rh,:co2,:hvac,:light,:plug,:total,
                :kwh,:cost,:sp,:comfort,:peak,NULL,:scn)
        ON CONFLICT (timestamp, zone_id) DO UPDATE SET
           total_power_kw=EXCLUDED.total_power_kw, hvac_power_kw=EXCLUDED.hvac_power_kw,
           lighting_power_kw=EXCLUDED.lighting_power_kw, plug_power_kw=EXCLUDED.plug_power_kw,
           energy_kwh=EXCLUDED.energy_kwh, cost_vnd=EXCLUDED.cost_vnd,
           temperature_c=EXCLUDED.temperature_c, humidity_pct=EXCLUDED.humidity_pct,
           co2_ppm=EXCLUDED.co2_ppm, setpoint_c=EXCLUDED.setpoint_c,
           occupancy_count=EXCLUDED.occupancy_count, occupancy_state=EXCLUDED.occupancy_state,
           comfort_risk=EXCLUDED.comfort_risk, peak_risk=EXCLUDED.peak_risk,
           scenario_id=EXCLUDED.scenario_id""")
    with db_conn() as conn:
        n0 = fetch_all(conn, "SELECT count(*) c FROM telemetry_zone_15m WHERE building_id=:b",
                       b=BUILDING_ID)[0]["c"]
        conn.execute(text("DELETE FROM telemetry_zone_15m WHERE building_id=:b"), {"b": BUILDING_ID})
        for i in range(0, len(records), 5000):
            conn.execute(ins, records[i:i + 5000])
        n1 = fetch_all(conn, "SELECT count(*) c, min(timestamp) lo, max(timestamp) hi "
                       "FROM telemetry_zone_15m WHERE building_id=:b", b=BUILDING_ID)[0]
    print(f"replaced telemetry: {n0:,} -> {n1['c']:,} rows; range {n1['lo']} .. {n1['hi']}")

    # scan anomalies over the last 24h of LOADED data (no replay dependency)
    from greenflow.agent.anomaly import scan_anomalies
    hi = n1["hi"]
    with db_conn() as conn:
        n_alerts = scan_anomalies(conn, BUILDING_ID, hi - timedelta(hours=24), hi)
    print(f"anomaly scan: {n_alerts} alerts written (window end {hi})")


if __name__ == "__main__":
    main()

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
from datetime import timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import duckdb  # noqa: E402
from sqlalchemy import text  # noqa: E402

from greenflow.db import db_conn, fetch_all  # noqa: E402

BUILDING_ID = uuid.UUID("b0000000-0000-0000-0000-000000000001")
TZ = timezone(timedelta(hours=7))  # Hà Nội; timestamp trong data là local naive
DUCKDB_PATH = os.environ.get(
    "DUCKDB_PATH",
    "/data/Dat_data/greenflow_final_mode_b_plus_openmeteo_2025_30min_patched-001.duckdb")
SCENARIO_ID = "openmeteo_2025_30min_baseline"
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


REPO_ENTITY_KEYS = [
    "zone_3jzuKaCoj7duM8YUpx6IdZ", "zone_3H2AkZFqzChQTN2UOTW_7V",
    "zone_1xBFBS5N18MfdblikYnUBD", "zone_0Q4MSUQx531vKL_w06AgFJ",
    "zone_3xtnrBUgHBCwRh_xfyB8zE", "zone_36Blhdds16DOgkiAVsP5oS",
    "zone_0tWM7C8ybBZQ4c5DL1_lzg", "zone_2EmhthfYTF_hx0gAAa2KtI",
    "zone_3xtnrBUgHBCwRh_xfyB626", "zone_0tWM7C8ybBZQ4c5DL1_lwj",
    "zone_3xtnrBUgHBCwRh_xfyB4IZ", "zone_3xtnrBUgHBCwRh_xfyB1VR",
    "zone_1xBFBS5N18MfdblikYnUB5", "zone_0Q4MSUQx531vKL_w06AgFH",
]


def main() -> None:
    # 1) zones trong Postgres: entity_key -> (uuid, floor_id, room_type, area)
    with db_conn() as conn:
        zrows = fetch_all(conn, """
            SELECT entity_key, id, floor_id, room_type, area_m2
            FROM zones WHERE building_id = :b""", b=BUILDING_ID)
    zmap = {r["entity_key"]: r for r in zrows}
    missing = [k for k in REPO_ENTITY_KEYS if k not in zmap]
    if missing:
        raise SystemExit(f"zones chưa seed: {missing} (chạy seed_demo trước)")
    tz_to_key = {"tz_" + k[len("zone_"):]: k for k in REPO_ENTITY_KEYS}
    tz_ids = list(tz_to_key)

    # 2) kéo timeseries thật cho 14 zone từ DuckDB
    print(f"reading DuckDB: {DUCKDB_PATH}")
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    ph = ",".join(["?"] * len(tz_ids))
    rows = con.execute(f"""
        SELECT timestamp, zone_id, zone_air_temp_c, zone_rh_pct, cooling_setpoint_c,
               final_hvac_electricity_kw, lights_electricity_kw, equipment_electricity_kw,
               final_total_zone_electricity_kw, final_total_zone_electricity_kwh_interval
        FROM final_ai_training_timeseries
        WHERE zone_id IN ({ph})
        ORDER BY timestamp""", tz_ids).fetchall()
    print(f"pulled {len(rows):,} rows ({len(tz_ids)} zones)")

    # 3) tải toà nhà theo timestamp -> ngưỡng peak_risk (so với đỉnh năm)
    bt: dict = {}
    for r in rows:
        bt[r[0]] = bt.get(r[0], 0.0) + (r[8] or 0.0)
    bpeak = max(bt.values()) if bt else 1.0
    print(f"building peak (14-zone): {bpeak:.1f} kW")

    # 4) transform -> tuples
    records = []
    for (ts, zid, temp, rh, sp, hvac, light, equip, total, kwh) in rows:
        key = tz_to_key[zid]
        z = zmap[key]
        dt = ts.replace(tzinfo=TZ)
        room = z["room_type"]
        dens = DENSITY.get(room, DEFAULT_DENSITY)
        cap = max(1.0, float(z["area_m2"] or 0) * dens)
        occ = round(float(z["area_m2"] or 0) * dens * occ_fraction(dt))
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
            "occ": occ, "st": state, "conf": 0.85, "temp": round(temp, 2),
            "rh": round(rh, 1), "co2": co2, "hvac": round(hvac, 4),
            "light": round(light, 4), "plug": round(equip, 4), "total": round(total, 4),
            "kwh": round(float(kwh or 0), 5), "cost": cost, "sp": round(sp, 2),
            "comfort": comfort, "peak": peak, "scn": SCENARIO_ID})

    # 5) ghi vào Postgres (thay telemetry cũ)
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

    # scan anomalies over the replay window so the alerts feature has real data
    from greenflow.agent.anomaly import scan_anomalies
    from greenflow.replayclock import anchor
    with db_conn() as conn:
        now = anchor(conn, BUILDING_ID)
        n_alerts = scan_anomalies(conn, BUILDING_ID, now - timedelta(hours=24), now)
    print(f"anomaly scan: {n_alerts} alerts written (window end {now})")


if __name__ == "__main__":
    main()

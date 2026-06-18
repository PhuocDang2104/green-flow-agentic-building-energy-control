"""Seed the demo building, telemetry, baseline simulation and scenarios.

Idempotent: wipes and reloads the demo building (fixed UUID) on each run.

Prerequisites:
  - Postgres up with db/schema.sql applied (docker compose up -d db)
  - db/seed/normalized_building.json (run scripts/build_3d_assets.py first;
    this script runs it automatically when missing)

Usage: python scripts/seed_demo.py [--days 7]
"""

from __future__ import annotations

import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import text  # noqa: E402

from greenflow.config import get_settings  # noqa: E402
from greenflow.db import db_conn  # noqa: E402
from greenflow.sim.actions import make_action  # noqa: E402
from greenflow.sim.kpi import compare_runs, run_cost_vnd, tariff_at  # noqa: E402
from greenflow.sim.synthetic_baseline import (outdoor_temp_c, run_synthetic,  # noqa: E402
                                              zone_specs_from_normalized)

BUILDING_ID = uuid.UUID("b0000000-0000-0000-0000-000000000001")
TZ = timezone(timedelta(hours=7))
SEED_FILE = ROOT / "db" / "seed" / "normalized_building.json"
OBJECT_MAP_FILE = (ROOT / "web" / "public" / "assets" / "buildings"
                   / "greenflow_archetype" / "mapping" / "xeokit_object_map.json")

rng = random.Random(42)


def load_normalized() -> dict:
    if not SEED_FILE.exists():
        print("normalized_building.json missing; running build_3d_assets.py ...")
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_3d_assets.py"),
                        "--skip-xkt"], check=True)
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def main(days: int = 7) -> None:
    normalized = load_normalized()
    with db_conn() as conn:
        print("Wiping previous demo building ...")
        conn.execute(text("DELETE FROM buildings WHERE id = :b"), {"b": BUILDING_ID})
        conn.execute(text("DELETE FROM weather_15m WHERE location_name = :n"),
                     {"n": normalized["building"]["location_name"]})

        print("Seeding building/floors/zones/devices ...")
        ids = seed_canonical(conn, normalized)

        print("Seeding entity relations ...")
        seed_relations(conn, normalized, ids)

        print("Seeding geometry assets + mesh map ...")
        seed_geometry(conn, ids)

        print("Seeding tariff rules ...")
        seed_tariffs(conn)

        print("Seeding demo CCTV cameras ...")
        seed_cameras(conn, normalized, ids)

        print(f"Seeding {days} days of 15-min telemetry ...")
        seed_telemetry(conn, normalized, ids, days)

        print("Seeding baseline + optimized simulation runs ...")
        seed_simulations(conn, normalized, ids)

        print("Seeding demo scenarios ...")
        seed_scenarios(conn)

    print("Done. Demo building id:", BUILDING_ID)


def seed_canonical(conn, normalized) -> dict:
    b = normalized["building"]
    conn.execute(text("""
        INSERT INTO buildings (id, name, location_name, timezone, building_type, source_dataset)
        VALUES (:id, :name, :loc, 'Asia/Ho_Chi_Minh', :btype, :src)
    """), {"id": BUILDING_ID, "name": b["name"], "loc": b["location_name"],
           "btype": b["building_type"], "src": b["source_dataset"]})

    floor_ids: dict[str, uuid.UUID] = {}
    for f in normalized["floors"]:
        fid = uuid.uuid4()
        floor_ids[f["entity_key"]] = fid
        conn.execute(text("""
            INSERT INTO floors (id, building_id, floor_index, name, elevation_m)
            VALUES (:id, :b, :idx, :name, :el)
        """), {"id": fid, "b": BUILDING_ID, "idx": f["floor_index"],
               "name": f["name"], "el": f["elevation_m"]})

    zone_ids: dict[str, uuid.UUID] = {}
    for z in normalized["zones"]:
        zid = uuid.uuid4()
        zone_ids[z["entity_key"]] = zid
        conn.execute(text("""
            INSERT INTO zones (id, building_id, floor_id, name, entity_key, room_type,
                               area_m2, volume_m3, comfort_profile, source_space_name)
            VALUES (:id, :b, :f, :name, :key, :rt, :area, :vol, :cp, :src)
        """), {"id": zid, "b": BUILDING_ID, "f": floor_ids[z["floor_key"]],
               "name": z["name"], "key": z["entity_key"], "rt": z["room_type"],
               "area": z["area_m2"], "vol": z["volume_m3"],
               "cp": z["comfort_profile"], "src": z["source_space_name"]})

    device_ids: dict[str, uuid.UUID] = {}
    for d in normalized["devices"]:
        did = uuid.uuid4()
        device_ids[d["entity_key"]] = did
        conn.execute(text("""
            INSERT INTO devices (id, building_id, floor_id, zone_id, device_type,
                                 device_subtype, name, entity_key, tag, controllable,
                                 risk_level, status, nominal_power_kw)
            VALUES (:id, :b, :f, :z, :dt, :ds, :name, :key, :tag, :ctl, :risk,
                    'online', :pw)
        """), {"id": did, "b": BUILDING_ID,
               "f": floor_ids.get(d.get("floor_key", ""), None),
               "z": zone_ids.get(d.get("zone_key") or "", None),
               "dt": d["device_type"], "ds": d["device_subtype"], "name": d["name"],
               "key": d["entity_key"], "tag": d["tag"], "ctl": d["controllable"],
               "risk": d["risk_level"], "pw": d["nominal_power_kw"]})

    return {"floors": floor_ids, "zones": zone_ids, "devices": device_ids}


def seed_relations(conn, normalized, ids) -> None:
    key_to_id = {
        "Building": {normalized["building"]["entity_key"]: BUILDING_ID},
        "Floor": ids["floors"],
        "Zone": ids["zones"],
        "Device": ids["devices"],
    }
    for r in normalized["entity_relations"]:
        src = key_to_id.get(r["src_type"], {}).get(r["src_key"])
        dst = key_to_id.get(r["dst_type"], {}).get(r["dst_key"])
        if not src or not dst:
            continue
        conn.execute(text("""
            INSERT INTO entity_relations (building_id, src_entity_type, src_entity_id,
                relation_type, dst_entity_type, dst_entity_id, confidence, method)
            VALUES (:b, :st, :s, :rel, :dt, :d, :conf, :m)
        """), {"b": BUILDING_ID, "st": r["src_type"], "s": src, "rel": r["relation"],
               "dt": r["dst_type"], "d": dst, "conf": r["confidence"], "m": r["method"]})


def seed_geometry(conn, ids) -> None:
    if not OBJECT_MAP_FILE.exists():
        print("  (object map missing, skipping mesh_entity_map)")
        return
    object_map = json.loads(OBJECT_MAP_FILE.read_text(encoding="utf-8"))
    layers = sorted({o["layer"] for o in object_map})
    asset_ids = {}
    for layer in layers:
        aid = uuid.uuid4()
        asset_ids[layer] = aid
        conn.execute(text("""
            INSERT INTO geometry_assets (id, building_id, layer, asset_url, metadata_url,
                                         asset_type, default_visible)
            VALUES (:id, :b, :layer, :url, :meta, 'xkt', :vis)
        """), {"id": aid, "b": BUILDING_ID, "layer": layer,
               "url": f"/assets/buildings/greenflow_archetype/xkt/{layer}.xkt",
               "meta": f"/assets/buildings/greenflow_archetype/metadata/{layer}_metadata.json",
               "vis": layer != "fenestration"})
    for o in object_map:
        entity_id = None
        if o["entity_type"] == "ThermalZone":
            entity_id = ids["zones"].get(o["entity_key"])
        props = {"name": o.get("name"), "room_type": o.get("room_type"),
                 "live": o.get("live", False)}
        conn.execute(text("""
            INSERT INTO mesh_entity_map (asset_id, building_id, mesh_id, entity_type,
                                         entity_id, entity_key, floor_id, layer, properties)
            VALUES (:a, :b, :mesh, :et, :eid, :ekey, NULL, :layer, cast(:p as jsonb))
        """), {"a": asset_ids[o["layer"]], "b": BUILDING_ID,
               "mesh": o["xeokit_object_id"], "et": o["entity_type"],
               "eid": entity_id, "ekey": o["entity_key"], "layer": o["layer"],
               "p": json.dumps(props)})


def seed_tariffs(conn) -> None:
    # Simplified EVN business tariff bands (mirrors sim/kpi.py)
    bands = [
        ("offpeak_night", 1184, "22:00", "23:59"),
        ("offpeak_early", 1184, "00:00", "04:00"),
        ("peak_morning", 3314, "09:30", "11:30"),
        ("peak_evening", 3314, "17:00", "20:00"),
        ("normal", 1839, None, None),
    ]
    for name, price, start, end in bands:
        conn.execute(text("""
            INSERT INTO tariff_rules (building_id, metric_type, unit_price, currency,
                                      peak_start, peak_end, effective_from)
            VALUES (:b, :mt, :p, 'VND', :ps, :pe, '2026-01-01')
        """), {"b": BUILDING_ID, "mt": f"electricity_{name}", "p": price,
               "ps": start, "pe": end})


# Per-zone CCTV mapping. Each clip is a real office/CCTV video annotated OFFLINE
# with YOLO person detection (bounding boxes + live people count overlay) — see
# scripts/annotate_cctv_yolo.py. video_source = /media/cctv/<file> -> served from
# MinIO via the API /media proxy (upload clips first: scripts/upload_media.py).
# Mapped by zone NAME so each space shows a fitting feed (conference->meeting,
# restaurant->restaurant, elevator->staircase, presentation->auditorium, ...).
CAMERA_CLIP_BY_ZONE_NAME = {
    "Open Office 220": "/media/cctv/open_office_1.webm",
    "Open Office 230": "/media/cctv/open_office_2.webm",
    "Open Office 330": "/media/cctv/open_office_3.webm",
    "Open Office 430": "/media/cctv/open_office_4.webm",
    "Meeting 547": "/media/cctv/meeting_room_1.webm",
    "Restaurant 1000": "/media/cctv/restaurant_1.webm",
    "Auditorium 130": "/media/cctv/auditorium_1.webm",
    "Business Space 140": "/media/cctv/business_1.webm",
    "Parking 150": "/media/cctv/security_1.webm",
    "Lobby 100": "/media/cctv/lobby_1.webm",
    "Staircase 201": "/media/cctv/elevator_1.webm",
    "Staircase 302": "/media/cctv/elevator_1.webm",
    "Staircase 401": "/media/cctv/elevator_1.webm",
    "Kitchen 110": "/media/cctv/kitchen_1.webm",
}


def seed_cameras(conn, normalized, ids) -> None:
    zone_ids = ids["zones"]
    for z in normalized["zones"]:
        video = CAMERA_CLIP_BY_ZONE_NAME.get(z["name"])
        if not video:
            continue
        conn.execute(text("""
            INSERT INTO cameras (id, building_id, floor_id, zone_id, name,
                                 video_source, privacy_mode)
            VALUES (:id, :b, :f, :z, :name, :src, 'count_only')
        """), {"id": uuid.uuid4(), "b": BUILDING_ID,
               "f": ids["floors"].get(z["floor_key"]),
               "z": zone_ids[z["entity_key"]],
               "name": f"CAM_{z['name']}", "src": video})


def seed_telemetry(conn, normalized, ids, days: int) -> None:
    specs = zone_specs_from_normalized(normalized)
    zone_ids = ids["zones"]
    floor_id = next(iter(ids["floors"].values()))
    # Pick two zones to carry demo anomalies (so the Building Semantic Agent has
    # findings). Chosen by room type from the real building, not hardcoded keys.
    by_type = {z["room_type"]: z["entity_key"] for z in normalized["zones"]}
    anomaly_light_zone = (by_type.get("meeting_room") or by_type.get("amenity")
                          or by_type.get("hallway") or specs[0].zone_key)
    anomaly_hvac_zone = (by_type.get("office") or by_type.get("open_office")
                         or specs[-1].zone_key)
    device_by_zone: dict[str, list[tuple[uuid.UUID, str, str]]] = {}
    for d in normalized["devices"]:
        if d.get("zone_key"):
            device_by_zone.setdefault(d["zone_key"], []).append(
                (ids["devices"][d["entity_key"]], d["device_subtype"], d["device_type"]))

    now = datetime.now(TZ).replace(minute=0, second=0, microsecond=0)
    start_day = (now - timedelta(days=days - 1)).replace(hour=0)

    zone_rows, device_rows, occ_rows, weather_rows = [], [], [], []
    location = normalized["building"]["location_name"]

    for day in range(days):
        day_start = start_day + timedelta(days=day)
        is_weekend = day_start.weekday() >= 5
        result = run_synthetic(specs, is_weekend=is_weekend)
        by_zone_step: dict[tuple[str, int], object] = {
            (r.zone_key, r.minutes): r for r in result.records}

        for step in range(96):
            ts = day_start + timedelta(minutes=step * 15)
            if ts > now:
                break
            hour = ts.hour + ts.minute / 60.0
            t_out = outdoor_temp_c(hour) + rng.uniform(-0.4, 0.4)
            weather_rows.append({
                "ts": ts, "loc": location, "temp": round(t_out, 1),
                "hum": round(68 + 12 * rng.random(), 0),
                "wind": round(1.5 + 2.5 * rng.random(), 1),
                "cloud": round(30 + 50 * rng.random(), 0),
                "solar": round(900 * max(0.0, __import__("math").sin(
                    __import__("math").pi * (hour - 6) / 12.5)) if 6 <= hour <= 18.5 else 0, 0),
            })

            for spec in specs:
                r = by_zone_step.get((spec.zone_key, step * 15))
                if r is None:
                    continue
                noise = 1.0 + rng.uniform(-0.06, 0.06)
                occupancy = max(0, round(r.occupancy_count * noise))
                lighting = round(r.lighting_kw * noise, 3)
                plug = round(r.plug_kw * noise, 3)
                hvac = round(r.hvac_kw * noise, 3)
                anomaly = None

                # Demo anomalies on the most recent weekday afternoon/evening:
                if day == days - 1 and not is_weekend:
                    if spec.zone_key == anomaly_light_zone and 18 <= hour < 21:
                        lighting = round(spec.area_m2 * spec.lights_w_m2 / 1000.0 * 0.9, 3)
                        occupancy = 0
                        anomaly = "lighting_on_empty_zone"
                    if spec.zone_key == anomaly_hvac_zone and 12 <= hour < 14:
                        hvac = round(max(hvac, spec.area_m2 * 0.05), 3)
                        occupancy = 0
                        anomaly = "hvac_on_empty_zone"

                total = round(lighting + plug + hvac, 3)
                energy = round(total * 0.25, 4)
                zone_rows.append({
                    "ts": ts, "b": BUILDING_ID, "f": floor_id,
                    "z": zone_ids[spec.zone_key],
                    "occ": occupancy,
                    "occ_state": "occupied" if occupancy > 0 else "empty",
                    "occ_conf": round(0.93 - 0.1 * rng.random(), 2),
                    "temp": r.temperature_c + round(rng.uniform(-0.2, 0.2), 2),
                    "hum": round(55 + 10 * rng.random(), 0),
                    "co2": round(420 + occupancy * 18 + 30 * rng.random(), 0),
                    "hvac": hvac, "light": lighting, "plug": plug,
                    "total": total, "energy": energy,
                    "cost": round(energy * tariff_at(hour), 0),
                    "setp": r.setpoint_c,
                    "comfort": "high" if r.comfort_violated else (
                        "watch" if r.temperature_c > 26.0 else "normal"),
                    "peak": "high" if total > 8 else ("watch" if total > 5 else "normal"),
                    "anomaly": anomaly,
                })
                occ_rows.append({
                    "ts": ts, "b": BUILDING_ID, "f": floor_id,
                    "z": zone_ids[spec.zone_key], "count": occupancy,
                    "occupied": occupancy > 0,
                    "conf": round(0.9 - 0.08 * rng.random(), 2),
                })
                for did, subtype, dtype in device_by_zone.get(spec.zone_key, []):
                    power = {"air_terminal": hvac, "lighting_circuit": lighting,
                             "plug_circuit": plug}.get(subtype, 0.0)
                    device_rows.append({
                        "ts": ts, "b": BUILDING_ID, "f": floor_id,
                        "z": zone_ids[spec.zone_key], "d": did, "dt": dtype,
                        "status": "running" if power > 0.05 else "idle",
                        "setp": r.setpoint_c if subtype == "air_terminal" else None,
                        "power": power, "energy": round(power * 0.25, 4),
                    })

    _bulk(conn, """
        INSERT INTO telemetry_zone_15m (timestamp, building_id, floor_id, zone_id,
            occupancy_count, occupancy_state, occupancy_confidence, temperature_c,
            humidity_pct, co2_ppm, hvac_power_kw, lighting_power_kw, plug_power_kw,
            total_power_kw, energy_kwh, cost_vnd, setpoint_c, comfort_risk, peak_risk,
            anomaly_label, scenario_id)
        VALUES (:ts, :b, :f, :z, :occ, :occ_state, :occ_conf, :temp, :hum, :co2,
                :hvac, :light, :plug, :total, :energy, :cost, :setp, :comfort, :peak,
                :anomaly, 'live_mock')
    """, zone_rows)
    _bulk(conn, """
        INSERT INTO telemetry_device_15m (timestamp, building_id, floor_id, zone_id,
            device_id, device_type, status, setpoint_c, power_kw, energy_kwh, scenario_id)
        VALUES (:ts, :b, :f, :z, :d, :dt, :status, :setp, :power, :energy, 'live_mock')
    """, device_rows)
    _bulk(conn, """
        INSERT INTO occupancy_zone_15m (timestamp, building_id, floor_id, zone_id,
            person_count, occupied, confidence, source_type)
        VALUES (:ts, :b, :f, :z, :count, :occupied, :conf, 'mock_yolo')
    """, occ_rows)
    _bulk(conn, """
        INSERT INTO weather_15m (timestamp, location_name, outdoor_temp_c, humidity_pct,
            wind_speed_mps, cloud_cover_pct, solar_w_m2)
        VALUES (:ts, :loc, :temp, :hum, :wind, :cloud, :solar)
        ON CONFLICT DO NOTHING
    """, weather_rows)
    print(f"  zone rows: {len(zone_rows)}, device rows: {len(device_rows)}")


def _bulk(conn, sql: str, rows: list[dict]) -> None:
    if rows:
        conn.execute(text(sql), rows)


def seed_simulations(conn, normalized, ids) -> None:
    specs = zone_specs_from_normalized(normalized)
    baseline = run_synthetic(specs)
    # Target the largest open-office zones for lighting; HVAC actions are
    # building-wide (empty target = all zones) so the demo comparison shows a
    # real saving regardless of the building source.
    big_office = [z["entity_key"] for z in sorted(
        normalized["zones"], key=lambda z: -(z.get("area_m2") or 0))[:4]]
    actions = [
        make_action("lighting_reduction", big_office, start_hour=12, end_hour=18,
                    reason="Lunch-dip and afternoon daylight allow dimming"),
        make_action("hvac_eco_mode", [], start_hour=13, end_hour=16,
                    reason="Raise setpoint 1C during the afternoon peak window"),
        make_action("pre_cooling", [], start_hour=11, end_hour=13,
                    reason="Charge thermal mass before the peak window"),
    ]
    optimized = run_synthetic(specs, actions)
    kpi = compare_runs(baseline, optimized)

    day = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    base_id = _insert_sim_run(conn, "baseline_fixed_schedule", "baseline", [], baseline, day)
    opt_id = _insert_sim_run(conn, "agent_optimized", "agent",
                             [a.to_dict() for a in actions], optimized, day)

    conn.execute(text("""
        INSERT INTO scenario_kpi (building_id, baseline_run_id, optimized_run_id,
            baseline_kwh, optimized_kwh, saving_kwh, saving_percent, cost_saving_vnd,
            peak_reduction_kw, comfort_violation_delta_min, co2_avoided_kg, details_json)
        VALUES (:b, :base, :opt, :bk, :ok, :sk, :sp, :cs, :pr, :cd, :co2,
                cast(:details as jsonb))
    """), {"b": BUILDING_ID, "base": base_id, "opt": opt_id,
           "bk": kpi["baseline_kwh"], "ok": kpi["optimized_kwh"],
           "sk": kpi["saving_kwh"], "sp": kpi["saving_percent"],
           "cs": kpi["cost_saving_vnd"], "pr": kpi["peak_reduction_kw"],
           "cd": kpi["comfort_violation_delta_min"], "co2": kpi["co2_avoided_kg"],
           "details": json.dumps(kpi)})
    print(f"  baseline {kpi['baseline_kwh']} kWh vs optimized {kpi['optimized_kwh']} kWh "
          f"(saving {kpi['saving_percent']}%)")


def _insert_sim_run(conn, label, kind, actions_json, result, day_start) -> uuid.UUID:
    run_id = uuid.uuid4()
    conn.execute(text("""
        INSERT INTO simulation_runs (id, building_id, baseline_label, run_kind, engine,
                                     actions_json, status, completed_at, notes)
        VALUES (:id, :b, :label, :kind, :engine, cast(:actions as jsonb), 'completed',
                now(), :notes)
    """), {"id": run_id, "b": BUILDING_ID, "label": label, "kind": kind,
           "engine": result.engine, "actions": json.dumps(actions_json),
           "notes": f"totals: {json.dumps(result.totals)}"})

    # Wide sim storage (spine merge, decision #3) via the shared helper.
    from greenflow.db import fetch_all
    from greenflow.sim.sim_store import write_run_rows
    zone_ids = {z["entity_key"]: z["id"] for z in fetch_all(
        conn, "SELECT id, entity_key FROM zones WHERE building_id = :b", b=BUILDING_ID)}
    write_run_rows(conn, run_id, result, zone_ids, day_start)
    return run_id


def seed_scenarios(conn) -> None:
    scenarios = [
        ("Normal weekday", "normal", "Typical office weekday, fixed schedules",
         {"horizon_minutes": 60}),
        ("Heatwave afternoon", "heatwave", "Outdoor +3C, peak cooling stress",
         {"outdoor_delta_c": 3, "horizon_minutes": 60}),
        ("After-hours audit", "after_hours", "Detect devices running outside work hours",
         {"window": [19, 23]}),
        ("Peak-hour strategy", "peak_strategy", "Pre-cool + eco mode in 13:00-16:00 window",
         {"peak_window": [13, 16]}),
    ]
    for name, stype, desc, cfg in scenarios:
        conn.execute(text("""
            INSERT INTO scenarios (building_id, name, scenario_type, description, config_json)
            VALUES (:b, :n, :t, :d, cast(:c as jsonb))
        """), {"b": BUILDING_ID, "n": name, "t": stype, "d": desc, "c": json.dumps(cfg)})


if __name__ == "__main__":
    days = 7
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    main(days)

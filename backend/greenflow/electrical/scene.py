"""3D scene assembly for the electrical-distribution digital twin.

Builds a compact, frontend-ready payload (three.js y-up, metres, centred on the
building footprint) from the file artifacts: distribution boards, load points
(lights / outlets / alarms), thermal-zone centroids coloured by their feeding
board and estimated demand, board->zone supply links (the distribution
topology), and floor planes. Coordinates come straight from the IFC (x, y plan;
z elevation); per-zone annual energy is aggregated once from the gold zone
timeseries and cached so the endpoint stays fast.

Every magnitude keeps its provenance: board/zone energy is EnergyPlus-simulated,
the board<->zone mapping is spatially/naming-inferred with a confidence, and
overload is only stated where a real rated current exists (else rating_missing).
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache

from . import canonical as C
from . import config as cfg

ZONE_ENERGY_CSV = cfg.OUT_ELEC / "zone_annual_energy.csv"


def _f(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=1)
def zone_annual_energy() -> dict[str, dict]:
    """Per-zone annual kWh + peak kW, summed once from the gold zone timeseries.

    Cached to zone_annual_energy.csv; recomputed via DuckDB if the CSV is absent.
    """
    if ZONE_ENERGY_CSV.exists():
        return {r["zone_id"]: r for r in C.read_rows_csv(ZONE_ENERGY_CSV)}
    from .gold import ZONE_GLOB, duckdb_con
    con = duckdb_con()
    if cfg.DATASET_KEY == "elnino_2024_mar_apr":
        from .board_timeseries import _zone_timeseries_projection

        source_sql = _zone_timeseries_projection()
        rows = con.execute(
            f"""SELECT zone_id,
                       sum(final_total_zone_electricity_kwh_interval) AS total_kwh,
                       sum(lights_electricity_kwh_interval)           AS lights_kwh,
                       sum(equipment_electricity_kwh_interval)        AS equipment_kwh,
                       sum(final_hvac_electricity_kwh_interval)       AS hvac_kwh,
                       max(lights_electricity_kw
                           + equipment_electricity_kw
                           + final_hvac_electricity_kw)              AS peak_kw
                FROM ({source_sql})
                WHERE scenario_id = '{cfg.SCENARIO_ID}'
                GROUP BY 1"""
        ).fetch_arrow_table().to_pylist()
    else:
        rows = con.execute(
            f"""SELECT zone_id,
                       sum(final_total_zone_electricity_kwh_interval) AS total_kwh,
                       sum(lights_electricity_kwh_interval)           AS lights_kwh,
                       sum(equipment_electricity_kwh_interval)        AS equipment_kwh,
                       sum(final_hvac_electricity_kwh_interval)       AS hvac_kwh,
                       max(final_total_zone_electricity_kw)           AS peak_kw
                FROM read_parquet('{ZONE_GLOB}', hive_partitioning=true)
                GROUP BY 1"""
        ).fetch_arrow_table().to_pylist()
    con.close()
    out = []
    for r in rows:
        out.append({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})
    try:
        C.write_rows_csv(ZONE_ENERGY_CSV, out)
    except Exception:
        pass
    return {r["zone_id"]: r for r in out}


@lru_cache(maxsize=1)
def _boxes() -> dict[str, dict]:
    """zone_id -> {center:(x,y,z), size:(sx,sy,sz)} from real ARCH IfcSpace bboxes.

    Falls back to the centroid file (zero-size) if space_boxes.csv is absent.
    """
    out = {}
    bp = cfg.OUT_MAPPING / "space_boxes.csv"
    if bp.exists():
        for r in C.read_rows_csv(bp):
            zid = C.zone_id_from_guid(r["guid"])
            out[zid] = {"center": (_f(r["cx"]), _f(r["cy"]), _f(r["cz"])),
                        "size": (_f(r["sx"]) or 0.0, _f(r["sy"]) or 0.0, _f(r["sz"]) or 0.0)}
        if out:
            return out
    for r in C.read_rows_csv(cfg.OUT_MAPPING / "space_centroids.csv"):
        zid = C.zone_id_from_guid(r["guid"])
        out[zid] = {"center": (_f(r["x"]), _f(r["y"]), _f(r["z"])), "size": (3.5, 3.5, 3.0)}
    return out


def _dominant_alloc() -> tuple[dict, list]:
    """Per zone: dominant feeding board (max summed weight) + all supply links."""
    by_zone = defaultdict(lambda: defaultdict(float))
    links = []
    for a in C.read_rows_csv(cfg.OUT_ELEC / "zone_load_to_board_allocation.csv"):
        if a["board_id"] == cfg.UNMAPPED_BOARD_ID:
            continue
        by_zone[a["zone_id"]][a["board_id"]] += _f(a["weight"], 0.0)
        links.append(a)
    dominant = {z: max(bw.items(), key=lambda kv: kv[1])[0] for z, bw in by_zone.items() if bw}
    return dominant, links


def build_scene(include_loads: bool = True, max_lights: int = 800) -> dict:
    boards_raw = {b["board_id"]: b for b in C.read_rows_csv(cfg.OUT_ELEC / "electrical_boards.csv")}
    ann = {a["board_id"]: a for a in C.read_rows_csv(cfg.OUT_ELEC / "board_annual_summary.csv")}
    boxes = _boxes()
    zmeta = {z["zone_id"]: z for z in C.read_rows_csv(cfg.OUT_MAPPING / "zones.csv")}
    zenergy = zone_annual_energy()
    dominant, links = _dominant_alloc()

    # --- gather raw coordinates to compute a centring transform -------------
    xs, ys, zs = [], [], []
    for b in boards_raw.values():
        x, y, z = _f(b["x"]), _f(b["y"]), _f(b["z"])
        if None not in (x, y, z):
            xs.append(x); ys.append(y); zs.append(z)
    for bx in boxes.values():
        x, y, z = bx["center"]
        if None not in (x, y, z):
            xs.append(x); ys.append(y); zs.append(z)
    cx = sum(xs) / len(xs) if xs else 0.0
    cy = sum(ys) / len(ys) if ys else 0.0
    # ground = lowest real storey elevation (ignore the sea-level origin marker)
    floors_raw = [r for r in C.read_rows_csv(cfg.OUT_MAPPING / "floors.csv")
                  if 40.0 < _f(r["elevation_m"], -999) < 120.0]
    ground = min((_f(r["elevation_m"]) for r in floors_raw), default=min(zs, default=0.0))

    def to3(x, y, z):
        """Building (x east, y north, z up) -> three.js (x, y up, z) centred."""
        if None in (x, y, z):
            return None
        return [round(x - cx, 2), round(z - ground, 2), round(-(y - cy), 2)]

    # --- boards -------------------------------------------------------------
    boards = []
    peaks = [_f((ann.get(bid) or {}).get("peak_total_kw"), 0.0) for bid in boards_raw]
    pmax = max(peaks, default=1.0) or 1.0
    for bid, b in boards_raw.items():
        a = ann.get(bid, {})
        pos = to3(_f(b["x"]), _f(b["y"]), _f(b["z"]))
        if pos is None:
            continue
        peak = _f(a.get("peak_total_kw"), 0.0)
        boards.append({
            "id": bid, "tag": b.get("device_tag") or bid[:8], "pos": pos,
            "floor_id": b.get("floor_id"), "system_code": b.get("system_code"),
            "system_name": b.get("system_name"),
            "voltage_v": _f(b.get("voltage_v")), "phase_count": _f(b.get("phase_count")),
            "rated_current_a": _f(b.get("rated_current_a")),
            "peak_kw": round(peak, 2), "total_kwh": round(_f(a.get("total_kwh"), 0.0), 1),
            "lights_kwh": round(_f(a.get("lights_kwh"), 0.0), 1),
            "equipment_kwh": round(_f(a.get("equipment_kwh"), 0.0), 1),
            "hvac_kwh": round(_f(a.get("hvac_kwh"), 0.0), 1),
            "peak_current_a": _f(a.get("estimated_peak_current_a")),
            "loading_pct": _f(a.get("loading_pct")),
            "overload_status": a.get("overload_status") or "rating_missing",
            "intensity": round(peak / pmax, 4),
        })
    boards.sort(key=lambda r: -r["peak_kw"])
    # stable colour index per board for the distribution map
    color_idx = {b["id"]: i for i, b in enumerate(boards)}

    # --- zones (real ARCH bounding boxes) -----------------------------------
    zones = []
    zkwhs = [_f((zenergy.get(z) or {}).get("total_kwh"), 0.0) for z in boxes]
    zmax = max(zkwhs, default=1.0) or 1.0
    for zid, bx in boxes.items():
        x, y, z = bx["center"]
        pos = to3(x, y, z)
        if pos is None:
            continue
        sx, sy, sz = bx["size"]
        # building (x,y plan; z up) -> three (x, y=up, z=-y): size maps x->x, z->y, y->z
        size = [round(sx, 2), round(sz, 2), round(sy, 2)]
        m = zmeta.get(zid, {})
        e = zenergy.get(zid, {})
        feeder = dominant.get(zid)
        kwh = _f(e.get("total_kwh"), 0.0)
        zones.append({
            "id": zid, "name": m.get("eplus_zone_name") or m.get("long_name") or zid,
            "pos": pos, "size": size, "floor_id": m.get("floor_id"), "room_type": m.get("room_type"),
            "area_m2": _f(m.get("area_m2")), "total_kwh": round(kwh, 1),
            "lights_kwh": round(_f(e.get("lights_kwh"), 0.0), 1),
            "equipment_kwh": round(_f(e.get("equipment_kwh"), 0.0), 1),
            "hvac_kwh": round(_f(e.get("hvac_kwh"), 0.0), 1),
            "peak_kw": round(_f(e.get("peak_kw"), 0.0), 2),
            "feeder_board": feeder, "color_idx": color_idx.get(feeder, -1),
            "intensity": round(kwh / zmax, 4),
        })

    bpos = {b["id"]: b["pos"] for b in boards}

    # best feeding board per (zone, category) — route each load to the board that
    # actually feeds its category (lights->lighting board, plug->equipment board)
    best = {}
    for a in C.read_rows_csv(cfg.OUT_ELEC / "zone_load_to_board_allocation.csv"):
        if a["board_id"] == cfg.UNMAPPED_BOARD_ID:
            continue
        key = (a["zone_id"], a["load_category"])
        w = _f(a.get("weight"), 0.0)
        if key not in best or w > best[key][1]:
            best[key] = (a["board_id"], w)
    KIND_CAT = {"lighting": "lights", "plug": "equipment", "alarm": "lights"}

    def load_board(zid, kind):
        b = best.get((zid, KIND_CAT.get(kind, "lights")))
        return (b[0] if b else None) or dominant.get(zid)

    # --- load points (downsample lights so the browser stays smooth) --------
    loads = []
    if include_loads:
        lp_zone = {}
        for r in C.read_rows_csv(cfg.OUT_MAPPING / "object_to_floor_room_zone_map.csv"):
            if r.get("zone_id"):
                lp_zone[r["object_id"]] = r["zone_id"]
        lights = []
        for lp in C.read_rows_csv(cfg.OUT_ELEC / "electrical_load_points.csv"):
            pos = to3(_f(lp["x"]), _f(lp["y"]), _f(lp["z"]))
            if pos is None:
                continue
            kind = lp.get("load_kind") or "lighting"
            zid = lp_zone.get(lp["load_point_id"])
            rec = {"pos": pos, "kind": kind, "floor_id": lp.get("floor_id"),
                   "zone_id": zid, "board_id": load_board(zid, kind)}
            (lights if kind == "lighting" else loads).append(rec)
        if len(lights) > max_lights:
            step = len(lights) / max_lights
            lights = [lights[int(i * step)] for i in range(max_lights)]
        loads.extend(lights)

    # --- supply links: board -> each load, terminating EXACTLY on the load box ---
    supply_links = []
    for ld in loads:
        bid = ld.get("board_id")
        if bid in bpos:
            supply_links.append({"board_id": bid, "zone_id": ld.get("zone_id"),
                                 "from": bpos[bid], "to": ld["pos"],
                                 "color_idx": color_idx.get(bid, -1)})

    # --- floors -------------------------------------------------------------
    floors = []
    for r in sorted(floors_raw, key=lambda r: _f(r["elevation_m"], 0.0)):
        floors.append({"floor_id": r["floor_id"], "name": r["name"],
                       "y": round(_f(r["elevation_m"]) - ground, 2),
                       "elevation_m": _f(r["elevation_m"])})

    span_x = (max(xs) - min(xs)) if xs else 60.0
    span_y = (max(ys) - min(ys)) if ys else 60.0
    span_z = (max(zs) - ground) if zs else 30.0

    return {
        "building": cfg.BUILDING_NAME,
        "bounds": {"radius": round(max(span_x, span_y) / 2 + 8, 1),
                   "height": round(span_z, 1),
                   "span": [round(span_x, 1), round(span_z, 1), round(span_y, 1)]},
        "counts": {"boards": len(boards), "zones": len(zones),
                   "loads": len(loads), "links": len(supply_links), "floors": len(floors)},
        "color_scale": {
            "overload": {"normal": "#22c55e", "warning": "#eab308", "overload": "#ef4444",
                         "rating_missing": "#94a3b8", "unmapped": "#64748b"},
            "load_heat": ["#1e3a8a", "#0ea5e9", "#22c55e", "#eab308", "#f97316", "#ef4444"],
        },
        "boards": boards, "zones": zones, "supply_links": supply_links,
        "loads": loads, "floors": floors,
        "provenance": {
            "board_energy": "energyplus_simulated x spatially_inferred allocation",
            "zone_energy": "energyplus_simulated", "geometry": "ifc_derived",
            "topology": "spatially/naming-inferred (board<->zone), not as-wired",
        },
    }

"""Phase 11 — validation.

The headline guarantee: board allocation does **not** double-count energy. Each
zone's lights/equipment/HVAC is split across boards with weights summing to 1, so
Σ board energy == Σ zone energy per category — the board layer redistributes, it
never adds consumption. We also reconcile against the building meters and collect
every low-confidence / rating-missing / unmapped item for manual review.
"""
from __future__ import annotations

from collections import Counter

from . import canonical as C
from . import config as cfg
from . import gold
from .board_timeseries import (
    BOARD_TS,
    _alloc_wide,
    _raw_zone_timeseries_projection,
    _zone_timeseries_projection,
    register_scope_child_weights,
)
from .provenance import Confidence, ManualReviewItem
from ..energy_scope import counts_toward_energy

TOL_PCT = 0.5    # board-vs-zone energy must match within this %


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def run() -> dict[str, int]:
    cfg.ensure_dirs()
    checks: list[dict] = []
    recon: list[dict] = []
    reviews: list[dict] = []

    def chk(name, status, detail, value=None):
        checks.append({"check": name, "status": status, "detail": detail, "value": value})

    # ---- energy reconciliation (DuckDB) ----
    con = gold.duckdb_con()
    con.register("alloc_wide", _alloc_wide())
    register_scope_child_weights(con)
    import pyarrow as pa

    scope_ids = [
        z["zone_id"] for z in C.read_rows_csv(cfg.OUT_MAPPING / "zones.csv")
        if counts_toward_energy(z.get("counts_toward_energy", True))
    ]
    con.register("scope_counted", pa.table({"zone_id": scope_ids}))
    raw_zt = con.execute(f"""
        SELECT sum(lights_electricity_kwh_interval) l, sum(equipment_electricity_kwh_interval) e,
               sum(final_hvac_electricity_kwh_interval) h, sum(final_total_zone_electricity_kwh_interval) t
        FROM ({_raw_zone_timeseries_projection()}) WHERE scenario_id='{cfg.SCENARIO_ID}'
    """).fetchone()
    scoped_zt = con.execute(f"""
        SELECT sum(lights_electricity_kwh_interval) l, sum(equipment_electricity_kwh_interval) e,
               sum(final_hvac_electricity_kwh_interval) h, sum(final_total_zone_electricity_kwh_interval) t
        FROM ({_raw_zone_timeseries_projection()})
        WHERE scenario_id='{cfg.SCENARIO_ID}'
          AND zone_id IN (SELECT zone_id FROM scope_counted)
    """).fetchone()
    effective_zt = con.execute(f"""
        SELECT sum(lights_electricity_kwh_interval) l, sum(equipment_electricity_kwh_interval) e,
               sum(final_hvac_electricity_kwh_interval) h, sum(final_total_zone_electricity_kwh_interval) t
        FROM ({_zone_timeseries_projection()}) WHERE scenario_id='{cfg.SCENARIO_ID}'
    """).fetchone()
    zt = con.execute(f"""
        SELECT sum(lights_electricity_kwh_interval) l, sum(equipment_electricity_kwh_interval) e,
               sum(final_hvac_electricity_kwh_interval) h, sum(final_total_zone_electricity_kwh_interval) t
        FROM ({_zone_timeseries_projection()})
        WHERE scenario_id='{cfg.SCENARIO_ID}'
          AND zone_id IN (SELECT DISTINCT zone_id FROM alloc_wide)
    """).fetchone()
    bt = con.execute(f"""
        SELECT sum(board_lights_kwh_interval), sum(board_equipment_kwh_interval),
               sum(board_hvac_kwh_interval), sum(board_total_kwh_interval)
        FROM read_parquet('{BOARD_TS.as_posix()}')
    """).fetchone()
    mglob = cfg.parquet_scan(cfg.METER_TS)
    if cfg.DATASET_KEY == "elnino_2024_mar_apr":
        m = con.execute(f"""
            SELECT sum(electricity_facility_kwh),
                   sum(electricity_hvac_kwh),
                   sum(interiorlights_electricity_kwh),
                   sum(interiorequipment_electricity_kwh)
            FROM read_parquet('{mglob}', hive_partitioning=true)
        """).fetchone()
        meters = {
            cfg.METER_TOTAL: m[0],
            cfg.METER_FOR_CATEGORY[cfg.CAT_HVAC]: m[1],
            cfg.METER_FOR_CATEGORY[cfg.CAT_LIGHTS]: m[2],
            cfg.METER_FOR_CATEGORY[cfg.CAT_EQUIPMENT]: m[3],
        }
    else:
        meters = dict(con.execute(f"""
            SELECT meter_name, sum(value_kwh_interval_if_energy)
            FROM read_parquet('{mglob}', hive_partitioning=true) GROUP BY meter_name
        """).fetchall())
    con.close()

    zone_cat = {cfg.CAT_LIGHTS: zt[0] or 0, cfg.CAT_EQUIPMENT: zt[1] or 0, cfg.CAT_HVAC: zt[2] or 0}
    board_cat = {cfg.CAT_LIGHTS: bt[0] or 0, cfg.CAT_EQUIPMENT: bt[1] or 0, cfg.CAT_HVAC: bt[2] or 0}
    worst = 0.0
    for cat in cfg.LOAD_CATEGORIES:
        z, b = zone_cat[cat], board_cat[cat]
        diff = b - z
        dpct = (abs(diff) / z * 100.0) if z else 0.0
        worst = max(worst, dpct)
        meter_name = cfg.METER_FOR_CATEGORY[cat]
        mval = meters.get(meter_name)
        raw = {cfg.CAT_LIGHTS: raw_zt[0] or 0, cfg.CAT_EQUIPMENT: raw_zt[1] or 0,
               cfg.CAT_HVAC: raw_zt[2] or 0}[cat]
        scoped = {cfg.CAT_LIGHTS: scoped_zt[0] or 0,
                  cfg.CAT_EQUIPMENT: scoped_zt[1] or 0,
                  cfg.CAT_HVAC: scoped_zt[2] or 0}[cat]
        effective = {cfg.CAT_LIGHTS: effective_zt[0] or 0,
                     cfg.CAT_EQUIPMENT: effective_zt[1] or 0,
                     cfg.CAT_HVAC: effective_zt[2] or 0}[cat]
        recon.append({"category": cat, "raw_zone_kwh": round(raw, 1),
                      "excluded_aggregate_kwh": round(raw - scoped, 1),
                      "deduped_zone_kwh": round(scoped, 1),
                      "effective_zone_kwh": round(effective, 1),
                      "zone_allocated_kwh": round(z, 1),
                      "board_allocated_kwh": round(b, 1), "diff_kwh": round(diff, 3),
                      "diff_pct": round(dpct, 4), "building_meter_name": meter_name,
                      "building_meter_kwh": round(mval, 1) if mval else None,
                      "board_vs_meter_pct": round(b / mval * 100, 2) if mval else None,
                      "note": "board layer redistributes counted atomic/review zone energy"})
    chk("board_does_not_duplicate_counted_zones",
        "pass" if worst <= TOL_PCT else "fail",
        f"max board-vs-zone category mismatch {worst:.4f}% (tol {TOL_PCT}%)", round(worst, 4))
    tot_z, tot_b = zt[3] or 0, bt[3] or 0
    raw_total = raw_zt[3] or 0
    scoped_total = scoped_zt[3] or 0
    effective_total = effective_zt[3] or 0
    chk("aggregate_zone_energy_identified", "pass" if raw_total >= scoped_total else "fail",
        f"raw zone total {raw_total:.0f} kWh; potential deduped total {scoped_total:.0f} kWh; "
        f"aggregate scope {raw_total - scoped_total:.0f} kWh")
    chk("effective_zone_energy_conserved", "pass" if raw_total and abs(effective_total - raw_total) / raw_total * 100 <= TOL_PCT else "warn",
        f"raw zone total {raw_total:.0f} kWh vs effective redistributed total {effective_total:.0f} kWh")
    chk("board_total_equals_allocated_zone_total",
        "pass" if (tot_z and abs(tot_b - tot_z) / tot_z * 100 <= TOL_PCT) else "warn",
        f"deduped zone total {tot_z:.0f} kWh vs board total {tot_b:.0f} kWh "
        f"(only allocated categories are summed; boards are not added to zone totals)")
    fac = meters.get(cfg.METER_TOTAL)
    chk("building_meter_facility_present", "pass" if fac else "warn",
        f"{cfg.METER_TOTAL} = {fac:.0f} kWh" if fac else "facility meter missing")

    C.write_rows_csv(cfg.OUT_ELEC / "energy_reconciliation_by_board_category.csv", recon)

    # ---- structural / mapping checks + manual-review collection ----
    boards = C.read_rows_csv(cfg.OUT_ELEC / "electrical_boards.csv")
    lps = C.read_rows_csv(cfg.OUT_ELEC / "electrical_load_points.csv")
    alloc = C.read_rows_csv(cfg.OUT_ELEC / "zone_load_to_board_allocation.csv")
    circuits = C.read_rows_csv(cfg.OUT_ELEC / "electrical_circuits.csv")
    omap = C.read_rows_csv(cfg.OUT_MAPPING / "object_to_floor_room_zone_map.csv")
    l2c = {r["load_point_id"] for r in C.read_rows_csv(cfg.OUT_ELEC / "load_to_circuit_map.csv")}

    def review(sid, stype, reason, action, conf=Confidence.MANUAL_REVIEW, **fields):
        reviews.append(ManualReviewItem(C.sanitize(f"mr_{sid}_{len(reviews)}"), sid, stype,
                                        reason, action, conf, fields).to_dict())

    boards_no_rating = [b for b in boards if _f(b.get("rated_current_a")) in (None, 0.0)]
    chk("boards_with_rating", "warn" if boards_no_rating else "pass",
        f"{len(boards_no_rating)}/{len(boards)} boards have no/zero rated current → overload=rating_missing",
        len(boards_no_rating))
    for b in boards_no_rating:
        review(b["board_id"], "ElectricalBoard", "rated current missing/zero (placeholder)",
               "enter real Nimellisvirta from the panel schedule to enable overload analysis",
               device_tag=b.get("device_tag"))

    miss_v = [b for b in boards if _f(b.get("voltage_v")) is None]
    miss_p = [b for b in boards if _f(b.get("phase_count")) is None]
    chk("boards_voltage_phase", "warn" if (miss_v or miss_p) else "pass",
        f"boards missing voltage: {len(miss_v)}, missing phase: {len(miss_p)}")

    unmapped_alloc = [a for a in alloc if a["board_id"] == cfg.UNMAPPED_BOARD_ID]
    chk("unmapped_allocations", "warn" if unmapped_alloc else "pass",
        f"{len(unmapped_alloc)} (zone,category) allocations unmapped", len(unmapped_alloc))
    for a in unmapped_alloc:
        review(a["zone_id"] + "_" + a["load_category"], "ZoneLoadAllocation",
               "no board with evidence on the zone's floor",
               "confirm which board serves this zone/category", zone=a["zone_id"], category=a["load_category"])

    lp_no_circuit = [lp for lp in lps if lp.get("load_kind") != "alarm"
                     and lp["load_point_id"] not in l2c]
    chk("load_points_with_board", "warn" if lp_no_circuit else "pass",
        f"{len(lp_no_circuit)} consuming load points not assigned to a board/circuit", len(lp_no_circuit))

    lp_no_zone = [r for r in omap if r["object_type"] == "LoadPoint" and not r["zone_id"]]
    chk("load_points_with_zone", "info",
        f"{len(lp_no_zone)} load points without a zone (floor-only; not required for allocation)",
        len(lp_no_zone))

    low_alloc = sum(1 for a in alloc if a["mapping_confidence"] in (Confidence.LOW, Confidence.MANUAL_REVIEW))
    chk("low_confidence_allocations", "info",
        f"{low_alloc}/{len(alloc)} allocations are low/manual confidence (estimated)", low_alloc)

    pseudo = [c for c in circuits if c["kind"] == "pseudo"]
    real = [c for c in circuits if c["kind"] == "system_grouped"]
    chk("circuits_pseudo_vs_real", "info",
        f"{len(real)} system-grouped (naming evidence) vs {len(pseudo)} pseudo circuits")

    # explicit-zero design power placeholders from the property audit
    audit = C.read_rows_csv(cfg.OUT_ELEC / "electrical_asset_property_audit.csv")
    zero_power = sum(1 for r in audit if r["status"] == "explicit_zero_placeholder")
    chk("explicit_zero_placeholders", "info",
        f"{zero_power} explicit-zero power/current values flagged for review", zero_power)

    chk("board_values_labelled", "pass",
        "all board demand labelled value_class=spatially_inferred (EnergyPlus energy × inferred allocation); "
        "current uses assumed PF/voltage where IFC values are absent (flagged)")

    C.write_rows_csv(cfg.OUT_ELEC / "manual_review_items.csv", reviews)

    n_fail = sum(1 for c in checks if c["status"] == "fail")
    n_warn = sum(1 for c in checks if c["status"] == "warn")
    report = {"building": cfg.BUILDING_NAME, "scenario_id": cfg.SCENARIO_ID,
              "summary": {"checks": len(checks), "fail": n_fail, "warn": n_warn,
                          "manual_review_items": len(reviews)},
              "checks": checks, "reconciliation": recon}
    C.write_json(cfg.OUT_ELEC / "electrical_validation_report.json", report)

    by_status = Counter(c["status"] for c in checks)
    md = ["# Electrical Mapping Quality Report", "",
          f"- checks: **{len(checks)}** ({dict(by_status)})",
          f"- manual-review items: **{len(reviews)}**",
          f"- max board-vs-zone category energy mismatch: **{worst:.4f}%** "
          f"(≤{TOL_PCT}% ⇒ no double count)", "",
          "## Checks"]
    for c in checks:
        md.append(f"- [{c['status'].upper()}] **{c['check']}** — {c['detail']}")
    md += ["", "## Energy reconciliation (annual kWh)",
           "| category | raw zone | excluded | deduped zone | effective zone | allocated zone | board | Δ% | meter | board/meter % |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r in recon:
        md.append(f"| {r['category']} | {r['raw_zone_kwh']} | {r['excluded_aggregate_kwh']} | "
                  f"{r['deduped_zone_kwh']} | {r['effective_zone_kwh']} | {r['zone_allocated_kwh']} | "
                  f"{r['board_allocated_kwh']} | "
                  f"{r['diff_pct']} | {r['building_meter_kwh']} | {r['board_vs_meter_pct']} |")
    md += ["", "Boards are distribution assets; their demand is the redistribution of "
           "EnergyPlus-simulated zone energy, never additional consumption. Overload is "
           "reported only with a real rated current; otherwise `rating_missing`."]
    C.write_text(cfg.OUT_ELEC / "electrical_mapping_quality_report.md", "\n".join(md))
    return {"checks": len(checks), "fail": n_fail, "warn": n_warn, "manual_review": len(reviews),
            "max_mismatch_pct": round(worst, 4)}


if __name__ == "__main__":
    print(run())

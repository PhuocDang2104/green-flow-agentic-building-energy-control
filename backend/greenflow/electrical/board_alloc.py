"""Phase 6 — allocate simulated zone loads to electrical boards.

Boards never create energy; they receive allocated downstream zone loads. The
allocation backbone is the IFC evidence we actually have:

- load points (light fixtures / outlets) carry a Finnish system code
  (``Järjestelmien tunnukset``) shared with the boards → group load points to a
  board on the same floor with a matching system code, nearest by coordinates
  (medium); else same-floor nearest board (low); else UNMAPPED + manual_review;
- a zone's lighting / plug load is then split across the boards of the load
  points physically in that zone (weighted by design power when present, else
  count); zones with no mapped load points fall back to the floor's dominant
  board for that category (low);
- HVAC has no IFC board link → a **pseudo HVAC circuit** on the floor's main
  board (low, manual_review).

Per (zone, category) weights always sum to 1. Circuits are one per
(board, category); ``kind`` distinguishes system-grouped from pseudo.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from . import canonical as C
from . import config as cfg
from . import gold
from .provenance import Confidence, ValueClass

_CONF_RANK = {Confidence.MANUAL_REVIEW: 0, Confidence.LOW: 1, Confidence.MEDIUM: 2,
              Confidence.HIGH: 3, Confidence.EXACT: 4}
_RANK_CONF = {v: k for k, v in _CONF_RANK.items()}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _nearest(px, py, cands):
    if px is None or py is None:
        return cands[0]
    best, bd = cands[0], 1e18
    for b in cands:
        bx, by = _f(b.get("x")), _f(b.get("y"))
        if bx is None or by is None:
            continue
        d = (px - bx) ** 2 + (py - by) ** 2
        if d < bd:
            best, bd = b, d
    return best


def run() -> dict[str, int]:
    cfg.ensure_dirs()
    boards = C.read_rows_csv(cfg.OUT_ELEC / "electrical_boards.csv")
    lps = C.read_rows_csv(cfg.OUT_ELEC / "electrical_load_points.csv")
    zones = C.read_rows_csv(cfg.OUT_MAPPING / "zones.csv")
    omap = {r["object_id"]: r for r in C.read_rows_csv(cfg.OUT_MAPPING / "object_to_floor_room_zone_map.csv")}
    zone_eplus = gold.zone_eplus_map()

    boards_by_floor: dict[str, list] = defaultdict(list)
    boards_by_floor_sys: dict[tuple, list] = defaultdict(list)
    for b in boards:
        boards_by_floor[b["floor_id"]].append(b)
        if b.get("system_code"):
            boards_by_floor_sys[(b["floor_id"], b["system_code"])].append(b)

    # ---- Step A: load point -> board ----
    lp_board: dict[str, tuple] = {}   # lp_id -> (board_id, method, confidence, system_code)
    for lp in lps:
        if lp.get("load_kind") == "alarm":
            continue
        floor, sys = lp["floor_id"], lp.get("system_code") or ""
        px, py = _f(lp.get("x")), _f(lp.get("y"))
        cands = boards_by_floor_sys.get((floor, sys)) if sys else None
        if cands:
            method, conf = "system_code+floor+nearest", Confidence.MEDIUM
        else:
            cands = boards_by_floor.get(floor) or []
            method, conf = "floor+nearest", Confidence.LOW
        if not cands:
            lp_board[lp["load_point_id"]] = (cfg.UNMAPPED_BOARD_ID, "unmapped",
                                             Confidence.MANUAL_REVIEW, sys)
        else:
            b = _nearest(px, py, cands)
            lp_board[lp["load_point_id"]] = (b["board_id"], method, conf, sys)

    # ---- circuits: one per (board, category) ----
    circuits: dict[str, dict] = {}

    def circuit_for(board_id: str, category: str) -> str:
        cid = C.circuit_id(f"{board_id}|{category}")
        circuits.setdefault(cid, {
            "circuit_id": cid, "board_id": board_id, "category": category,
            "kind": "pseudo", "system_codes": set(), "load_point_count": 0,
            "confidence": Confidence.LOW})
        return cid

    load_to_circuit: list[dict] = []
    lp_by_zone_cat: dict[tuple, list] = defaultdict(list)
    floor_cat_counter: dict[tuple, Counter] = defaultdict(Counter)
    lp_index = {lp["load_point_id"]: lp for lp in lps}

    for lp in lps:
        if lp.get("load_kind") == "alarm":
            continue
        lpid = lp["load_point_id"]
        bid, method, conf, sys = lp_board[lpid]
        cat = lp.get("category") or "other"
        if cat not in (cfg.CAT_LIGHTS, cfg.CAT_EQUIPMENT):
            continue
        cid = circuit_for(bid, cat)
        c = circuits[cid]
        c["load_point_count"] += 1
        if sys:
            c["system_codes"].add(sys)
        if conf == Confidence.MEDIUM:
            c["kind"] = "system_grouped"
            c["confidence"] = Confidence.MEDIUM
        load_to_circuit.append({"load_point_id": lpid, "circuit_id": cid, "board_id": bid,
                                "category": cat, "system_code": sys, "mapping_method": method,
                                "mapping_confidence": conf})
        zone = omap.get(lpid, {}).get("zone_id", "")
        lp_by_zone_cat[(zone, cat)].append((lp, bid, conf))
        floor_cat_counter[(lp["floor_id"], cat)][bid] += 1

    floor_cat_board = {k: cnt.most_common(1)[0][0] for k, cnt in floor_cat_counter.items() if cnt}

    # fallback infrastructure: dominant board per floor, and nearest floor with boards
    board_lp_count = Counter(bid for (bid, _m, _c, _s) in lp_board.values())
    floor_any_board = {fl: max(bs, key=lambda b: board_lp_count.get(b["board_id"], 0))["board_id"]
                       for fl, bs in boards_by_floor.items() if bs}
    floors_meta = {f["floor_id"]: int(f["floor_index"])
                   for f in C.read_rows_csv(cfg.OUT_MAPPING / "floors.csv")
                   if str(f.get("floor_index", "")).strip() != ""}
    boarded_floors = [fl for fl, bs in boards_by_floor.items() if bs]

    def nearest_floor_board(floor):
        fi = floors_meta.get(floor)
        if fi is None:
            return None
        best = min(boarded_floors, key=lambda fl: abs(floors_meta.get(fl, 1e9) - fi), default=None)
        return floor_any_board.get(best) if best else None

    def pick_fallback(floor, cat):
        b = floor_cat_board.get((floor, cat))
        if b:
            return b, f"floor_dominant_{cat}", Confidence.LOW
        b = floor_cat_board.get((floor, cfg.CAT_LIGHTS))
        if b:
            return b, "floor_lighting_board_proxy", Confidence.LOW
        b = floor_any_board.get(floor)
        if b:
            return b, "floor_any_board", Confidence.LOW
        b = nearest_floor_board(floor)
        if b:
            return b, "nearest_floor_board", Confidence.LOW
        return cfg.UNMAPPED_BOARD_ID, "unmapped", Confidence.MANUAL_REVIEW

    # ---- Step B: zone x category allocation ----
    alloc: list[dict] = []

    def add_alloc(zid, ez, cat, weights, method, conf, evidence):
        total = sum(weights.values()) or 1.0
        norm = [(bid, round(w / total, 6)) for bid, w in weights.items()]
        # absorb rounding residual into the largest weight so the split sums to 1
        resid = round(1.0 - sum(w for _, w in norm), 6)
        if norm:
            i = max(range(len(norm)), key=lambda k: norm[k][1])
            norm[i] = (norm[i][0], round(norm[i][1] + resid, 6))
        for bid, w in norm:
            alloc.append({
                "zone_id": zid, "eplus_zone_name": ez, "load_category": cat,
                "board_id": bid, "circuit_id": circuit_for(bid, cat), "phase": "",
                "weight": w, "mapping_method": method,
                "mapping_confidence": conf, "value_class": ValueClass.SPATIALLY_INFERRED
                if "load_point" in method else ValueClass.NAMING_INFERRED if "system" in method
                else ValueClass.ASSUMPTION_BASED,
                "evidence": json.dumps(evidence, ensure_ascii=False, default=str),
                "notes": "" if bid != cfg.UNMAPPED_BOARD_ID else "no board evidence",
            })

    for z in zones:
        zid, floor = z["zone_id"], z["floor_id"]
        ez = zone_eplus.get(zid, z.get("eplus_zone_name", ""))
        for cat in (cfg.CAT_LIGHTS, cfg.CAT_EQUIPMENT):
            group = lp_by_zone_cat.get((zid, cat), [])
            weights: dict[str, float] = defaultdict(float)
            confs = []
            syscodes = set()
            for (lp, bid, conf) in group:
                p = _f(lp.get("design_power_w")) or 0.0
                weights[bid] += p if p > 0 else 1.0
                confs.append(_CONF_RANK[conf])
                if lp.get("system_code"):
                    syscodes.add(lp["system_code"])
            if weights:
                conf = _RANK_CONF[min(confs)]
                add_alloc(zid, ez, cat, dict(weights), "load_point_aggregation", conf,
                          {"n_load_points": len(group), "n_boards": len(weights),
                           "system_codes": sorted(syscodes)})
            else:
                bid, method, conf = pick_fallback(floor, cat)
                add_alloc(zid, ez, cat, {bid: 1.0}, method, conf,
                          {"reason": "no load points of this category in zone"})
        # HVAC — pseudo circuit on the floor's main board (no IFC HVAC->board link)
        bid, _m, _c = pick_fallback(floor, cfg.CAT_LIGHTS)
        cid = circuit_for(bid, cfg.CAT_HVAC)
        circuits[cid]["kind"] = "pseudo"
        add_alloc(zid, ez, cfg.CAT_HVAC, {bid: 1.0}, "pseudo_hvac_floor_main",
                  Confidence.LOW if bid != cfg.UNMAPPED_BOARD_ID else Confidence.MANUAL_REVIEW,
                  {"reason": "no IFC HVAC->board link; pseudo HVAC circuit (estimated)"})

    # ---- write circuits / maps / allocation ----
    circ_rows = []
    c2b_rows = []
    for cid, c in circuits.items():
        circ_rows.append({"circuit_id": cid, "board_id": c["board_id"], "category": c["category"],
                          "kind": c["kind"], "system_codes": ",".join(sorted(c["system_codes"])),
                          "load_point_count": c["load_point_count"], "confidence": c["confidence"],
                          "value_class": ValueClass.NAMING_INFERRED if c["kind"] == "system_grouped"
                          else ValueClass.ASSUMPTION_BASED,
                          "notes": "system-grouped circuit (naming evidence)" if c["kind"] == "system_grouped"
                          else "pseudo circuit (estimated)"})
        c2b_rows.append({"circuit_id": cid, "board_id": c["board_id"], "category": c["category"],
                         "kind": c["kind"], "confidence": c["confidence"]})

    C.write_rows_csv(cfg.OUT_ELEC / "electrical_circuits.csv", circ_rows)
    C.write_rows_csv(cfg.OUT_ELEC / "load_to_circuit_map.csv", load_to_circuit)
    C.write_rows_csv(cfg.OUT_ELEC / "circuit_to_board_map.csv", c2b_rows)
    C.write_rows_csv(cfg.OUT_ELEC / "zone_load_to_board_allocation.csv", alloc)

    _report(alloc, circ_rows, lp_board, boards)
    return {"allocations": len(alloc), "circuits": len(circ_rows),
            "load_to_circuit": len(load_to_circuit), "boards": len(boards)}


def _report(alloc, circuits, lp_board, boards) -> None:
    by_cat = Counter(a["load_category"] for a in alloc)
    by_conf = Counter(a["mapping_confidence"] for a in alloc)
    unmapped = sum(1 for a in alloc if a["board_id"] == cfg.UNMAPPED_BOARD_ID)
    # weight-sum check per (zone, category)
    sums = defaultdict(float)
    for a in alloc:
        sums[(a["zone_id"], a["load_category"])] += float(a["weight"])
    bad = [k for k, v in sums.items() if abs(v - 1.0) > 1e-6]
    lp_conf = Counter(c for (_b, _m, c, _s) in lp_board.values())
    real = sum(1 for c in circuits if c["kind"] == "system_grouped")
    lines = [
        "# Allocation Quality Report", "",
        f"- allocation rows: **{len(alloc)}** (per zone×category)",
        f"- by category: {dict(by_cat)}",
        f"- by mapping confidence: {dict(by_conf)}",
        f"- allocations to UNMAPPED_BOARD (manual review): **{unmapped}**",
        f"- (zone,category) weight-sum ≠ 1: **{len(bad)}** (must be 0)", "",
        "## Load-point → board",
        f"- by confidence: {dict(lp_conf)}", "",
        "## Circuits",
        f"- total circuits: **{len(circuits)}** "
        f"(system-grouped: **{real}**, pseudo: **{len(circuits) - real}**)", "",
        "Lighting/plug use IFC system-code + floor + proximity evidence; HVAC uses a",
        "pseudo HVAC circuit on the floor main board (no IFC HVAC→board link). Boards",
        "are distribution assets and are never counted as additional consumption.",
    ]
    C.write_text(cfg.OUT_ELEC / "allocation_quality_report.md", "\n".join(lines))


if __name__ == "__main__":
    print(run())

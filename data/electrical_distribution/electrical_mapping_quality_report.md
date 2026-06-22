# Electrical Mapping Quality Report

- checks: **12** ({'pass': 7, 'warn': 1, 'info': 4})
- manual-review items: **57**
- max board-vs-zone category energy mismatch: **0.0000%** (≤0.5% ⇒ no double count)

## Checks
- [PASS] **no_double_count_by_category** — max board-vs-zone category mismatch 0.0000% (tol 0.5%)
- [PASS] **board_total_equals_allocated_zone_total** — zone total 3106609 kWh vs board total 3106609 kWh (only allocated categories are summed; boards are not added to zone totals)
- [PASS] **building_meter_facility_present** — Electricity:Facility = 3106609 kWh
- [WARN] **boards_with_rating** — 57/57 boards have no/zero rated current → overload=rating_missing
- [PASS] **boards_voltage_phase** — boards missing voltage: 0, missing phase: 0
- [PASS] **unmapped_allocations** — 0 (zone,category) allocations unmapped
- [PASS] **load_points_with_board** — 0 consuming load points not assigned to a board/circuit
- [INFO] **load_points_with_zone** — 0 load points without a zone (floor-only; not required for allocation)
- [INFO] **low_confidence_allocations** — 766/1032 allocations are low/manual confidence (estimated)
- [INFO] **circuits_pseudo_vs_real** — 54 system-grouped (naming evidence) vs 26 pseudo circuits
- [INFO] **explicit_zero_placeholders** — 635 explicit-zero power/current values flagged for review
- [PASS] **board_values_labelled** — all board demand labelled value_class=spatially_inferred (EnergyPlus energy × inferred allocation); current uses assumed PF/voltage where IFC values are absent (flagged)

## Energy reconciliation (annual kWh)
| category | zone | board | Δ% | meter | board/meter % |
|---|---|---|---|---|---|
| lights | 1220855.4 | 1220855.4 | 0.0 | 1220855.4 | 100.0 |
| equipment | 1038181.5 | 1038181.5 | 0.0 | 1038181.5 | 100.0 |
| hvac | 847572.3 | 847572.3 | 0.0 | 847572.3 | 100.0 |

Boards are distribution assets; their demand is the redistribution of EnergyPlus-simulated zone energy, never additional consumption. Overload is reported only with a real rated current; otherwise `rating_missing`.
"""Regrettable-substitution check (spine merge — docs/spine/DECISIONS_AND_CRITIQUE.md D8).

An action is a "regrettable substitution" when it improves the target KPI while
degrading another dimension beyond threshold. Operates on the KPI dict produced
by sim.kpi.compare_runs (baseline vs optimized), so every rule is grounded in
simulated numbers, not heuristics:

  R1 comfort:        comfort_violation_delta_min > max_comfort_delta_min
                     (trading comfort for energy)
  R2 rebound:        rebound_kwh > rebound_ratio_max x saving_kwh
                     (load shifted to a later window — recool spike after
                     setback, pre-cool costing more than the peak it shaves).
                     Only evaluated when the engine reports `rebound_kwh`;
                     the synthetic engine simulates the full day so the
                     rebound is already inside saving_kwh, hence optional.
  R3 new peak:       peak_reduction_kw < -max_peak_increase_kw
                     (kWh saved but a new, higher peak created)
  R4 cost inversion: saving_kwh > 0 but cost_saving_vnd < 0
                     (kWh saved off-peak yet bill increases — optimized the
                     wrong objective under the tariff)

A flagged action must never auto-run; it escalates to approval with explicit
flags so the operator sees *why* the trade-off is suspect.
"""

from __future__ import annotations

from typing import Any

DEFAULT_THRESHOLDS = {
    "max_comfort_delta_min": 15.0,
    "rebound_ratio_max": 0.5,
    "max_peak_increase_kw": 5.0,
}


def regrettable_substitution_check(kpi: dict, thresholds: dict | None = None) -> dict[str, Any]:
    """Evaluate R1-R4 on a compare_runs() KPI dict.

    Returns {"passed": bool, "flags": [{dimension, value, threshold, message}]}.
    Missing KPI keys are treated as "no evidence" and skipped, so the check is
    safe to call with partial data (it only flags what it can prove).
    """
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    flags: list[dict] = []

    comfort_delta = kpi.get("comfort_violation_delta_min")
    if comfort_delta is not None and comfort_delta > t["max_comfort_delta_min"]:
        flags.append({
            "dimension": "comfort",
            "value": comfort_delta,
            "threshold": t["max_comfort_delta_min"],
            "message": (f"Comfort violation increases {comfort_delta:.0f} min "
                        f"(limit {t['max_comfort_delta_min']:.0f}): trading comfort for energy"),
        })

    saving_kwh = kpi.get("saving_kwh") or 0.0
    rebound_kwh = kpi.get("rebound_kwh")
    if rebound_kwh is not None and saving_kwh > 0 \
            and rebound_kwh > t["rebound_ratio_max"] * saving_kwh:
        flags.append({
            "dimension": "rebound",
            "value": rebound_kwh,
            "threshold": t["rebound_ratio_max"] * saving_kwh,
            "message": (f"Rebound {rebound_kwh:.1f} kWh erodes more than "
                        f"{t['rebound_ratio_max']:.0%} of the {saving_kwh:.1f} kWh saving"),
        })

    peak_reduction = kpi.get("peak_reduction_kw")
    if peak_reduction is not None and peak_reduction < -t["max_peak_increase_kw"]:
        flags.append({
            "dimension": "peak",
            "value": -peak_reduction,
            "threshold": t["max_peak_increase_kw"],
            "message": (f"Action creates a new peak +{-peak_reduction:.1f} kW "
                        f"(limit {t['max_peak_increase_kw']:.1f} kW)"),
        })

    cost_saving = kpi.get("cost_saving_vnd")
    if cost_saving is not None and saving_kwh > 0 and cost_saving < 0:
        flags.append({
            "dimension": "cost",
            "value": cost_saving,
            "threshold": 0,
            "message": (f"Saves {saving_kwh:.1f} kWh but costs {-cost_saving:,.0f} VND more "
                        "under the tariff: optimized the wrong objective"),
        })

    return {"passed": not flags, "flags": flags}

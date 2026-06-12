"""KPI comparison between two simulation runs (baseline vs agent/optimized).

Both runs must share weather/occupancy assumptions (the synthetic engine is
deterministic, so this holds by construction) — the delta is then attributable
to the applied actions only.
"""

from __future__ import annotations

from .synthetic_baseline import SimResult

CO2_KG_PER_KWH = 0.6766  # Vietnam grid emission factor

# Simplified EVN business tariff (VND/kWh)
TARIFF_OFFPEAK = 1184
TARIFF_NORMAL = 1839
TARIFF_PEAK = 3314


def tariff_at(hour: float) -> int:
    if hour < 4 or hour >= 22:
        return TARIFF_OFFPEAK
    if (9.5 <= hour < 11.5) or (17 <= hour < 20):
        return TARIFF_PEAK
    return TARIFF_NORMAL


def run_cost_vnd(result: SimResult) -> float:
    step_h = result.step_minutes / 60.0
    cost = 0.0
    for r in result.records:
        hour = (r.minutes % 1440) / 60.0
        cost += r.total_kw * step_h * tariff_at(hour)
    return round(cost, 0)


def peak_window_demand_kw(result: SimResult, start_hour: float = 13.0,
                          end_hour: float = 16.0) -> float:
    """Max building demand within a window (default afternoon peak)."""
    by_step: dict[int, float] = {}
    for r in result.records:
        hour = (r.minutes % 1440) / 60.0
        if start_hour <= hour < end_hour:
            by_step[r.minutes] = by_step.get(r.minutes, 0.0) + r.total_kw
    return round(max(by_step.values()), 2) if by_step else 0.0


def compare_runs(baseline: SimResult, optimized: SimResult) -> dict:
    b, o = baseline.totals, optimized.totals
    saving_kwh = b["energy_kwh"] - o["energy_kwh"]
    cost_b, cost_o = run_cost_vnd(baseline), run_cost_vnd(optimized)
    peak_b = peak_window_demand_kw(baseline)
    peak_o = peak_window_demand_kw(optimized)
    return {
        "baseline_kwh": b["energy_kwh"],
        "optimized_kwh": o["energy_kwh"],
        "saving_kwh": round(saving_kwh, 2),
        "saving_percent": round(100.0 * saving_kwh / b["energy_kwh"], 1) if b["energy_kwh"] else 0.0,
        "baseline_cost_vnd": cost_b,
        "optimized_cost_vnd": cost_o,
        "cost_saving_vnd": round(cost_b - cost_o, 0),
        "baseline_peak_kw": b["peak_demand_kw"],
        "optimized_peak_kw": o["peak_demand_kw"],
        "peak_reduction_kw": round(peak_b - peak_o, 2),
        "peak_window_baseline_kw": peak_b,
        "peak_window_optimized_kw": peak_o,
        "comfort_violation_baseline_min": b["comfort_violation_minutes"],
        "comfort_violation_optimized_min": o["comfort_violation_minutes"],
        "comfort_violation_delta_min": (o["comfort_violation_minutes"]
                                        - b["comfort_violation_minutes"]),
        "co2_avoided_kg": round(saving_kwh * CO2_KG_PER_KWH, 1),
        "hvac_kwh_delta": round(o["hvac_kwh"] - b["hvac_kwh"], 2),
        "lighting_kwh_delta": round(o["lighting_kwh"] - b["lighting_kwh"], 2),
    }

"""Period (campaign) what-if: building WITHOUT AI vs WITH a fixed AI policy across
a whole date range, using the structural (no-lag) zone surrogate for the
counterfactual.

baseline  = measured (M&V) building power over the period.
with-AI   = measured MINUS the surrogate-predicted reduction from the policy's
            setpoint change during its active hours (the pure elasticity delta
            applied to real measurement).

Unlike the in-loop one-shot sim (decision approval), this rolls ONE FIXED policy
across every step of the period — not re-deciding each day. Pure function so it
serves either the El Niño DuckDB (offline) or telemetry+weather (live).
"""
from __future__ import annotations

import numpy as np

from .model_registry import load_model

GRID_CO2_KG_PER_KWH = 0.6766
COMFORT_LIMIT_C = 26.5


def _tariff_vnd(hour: float) -> int:
    if hour < 4 or hour >= 22:
        return 1184
    if (9.5 <= hour < 11.5) or (17 <= hour < 20):
        return 3314
    return 1839


def _frame(df, feats, setpoint):
    import pandas as pd
    h = df["hour"].to_numpy(); dow = df["dow"].to_numpy(); mon = df["month"].to_numpy()
    full = {
        "outdoor_temp_c": df["outdoor_temp_c"], "outdoor_rh_pct": df["outdoor_rh_pct"],
        "global_horizontal_radiation_wh_m2": df["ghi"], "wind_speed_m_s": df["wind"],
        "cloud_cover_pct": df["cloud"],
        "hour_sin": np.sin(2 * np.pi * h / 24), "hour_cos": np.cos(2 * np.pi * h / 24),
        "dayofweek_sin": np.sin(2 * np.pi * dow / 7), "dayofweek_cos": np.cos(2 * np.pi * dow / 7),
        "month_sin": np.sin(2 * np.pi * mon / 12), "month_cos": np.cos(2 * np.pi * mon / 12),
        "office_hours_flag": df["office_hours_flag"],
        "cooling_setpoint_c": setpoint,
        "area_m2": df["area_m2"], "volume_m3": df["volume_m3"],
        "ceiling_height_m": df["ceiling_height_m"],
    }
    return pd.DataFrame({k: full[k] for k in feats})


def compute_campaign(df, *, setpoint_delta: float = 1.0, peak_start: int = 13,
                     peak_end: int = 16, step_min: int = 30) -> dict | None:
    """df: one row per (timestamp, zone) with columns: timestamp, hour, dow, month,
    total_power_kw, temperature_c, occupancy_count, cooling_setpoint_c, area_m2,
    volume_m3, ceiling_height_m, outdoor_temp_c, outdoor_rh_pct, ghi, wind, cloud,
    office_hours_flag. Returns {policy, kpi, daily:[...]} or None if no model."""
    loaded = load_model("zone")
    if loaded is None or loaded.model is None:
        return None
    booster, feats = loaded.model, loaded.features
    step_h = step_min / 60.0

    # Postgres NUMERIC -> Decimal -> pandas 'object'; LightGBM needs float. Coerce.
    import pandas as pd
    df = df.copy()
    for c in ("total_power_kw", "temperature_c", "occupancy_count", "cooling_setpoint_c",
              "area_m2", "volume_m3", "ceiling_height_m", "outdoor_temp_c", "outdoor_rh_pct",
              "ghi", "wind", "cloud", "hour", "dow", "month", "office_hours_flag"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)

    active = ((df["hour"] >= peak_start) & (df["hour"] < peak_end)
              & (df["dow"] < 5)).to_numpy()
    base_sp = df["cooling_setpoint_c"].to_numpy(dtype=float)
    act_sp = base_sp + np.where(active, setpoint_delta, 0.0)

    pred_base = np.clip(booster.predict(_frame(df, feats, base_sp)), 0, None)
    pred_act = np.clip(booster.predict(_frame(df, feats, act_sp)), 0, None)
    reduction = np.where(active, np.clip(pred_base - pred_act, 0, None), 0.0)

    measured = df["total_power_kw"].to_numpy(dtype=float)
    optimized = np.clip(measured - reduction, 0, None)

    occ = df["occupancy_count"].to_numpy(dtype=float)
    temp = df["temperature_c"].to_numpy(dtype=float)
    hour = df["hour"].to_numpy(dtype=float)
    # comfort cost: occupied active steps pushed over the limit by the setpoint rise
    new_violation = active & (occ >= 0.5) & (temp <= COMFORT_LIMIT_C) \
        & (temp + setpoint_delta > COMFORT_LIMIT_C)
    comfort_delta_min = float(new_violation.sum()) * step_min

    import pandas as pd
    g = pd.DataFrame({
        "date": pd.to_datetime(df["timestamp"]).dt.date,
        "ts": df["timestamp"], "base": measured, "opt": optimized,
        "cost_base": measured * step_h * np.array([_tariff_vnd(h) for h in hour]),
        "cost_opt": optimized * step_h * np.array([_tariff_vnd(h) for h in hour]),
    })
    # building total per timestamp (for daily peak)
    bt = g.groupby("ts").agg(base=("base", "sum"), opt=("opt", "sum"))
    peak = bt.groupby(pd.to_datetime(bt.index).date).max()
    daily = g.groupby("date").agg(
        base_kwh=("base", lambda s: float(s.sum() * step_h)),
        opt_kwh=("opt", lambda s: float(s.sum() * step_h)),
    )
    daily["peak_base_kw"] = peak["base"].round(2).values
    daily["peak_opt_kw"] = peak["opt"].round(2).values
    daily_list = [{"date": str(d), "baseline_kwh": round(r.base_kwh, 1),
                   "optimized_kwh": round(r.opt_kwh, 1),
                   "peak_baseline_kw": float(r.peak_base_kw),
                   "peak_optimized_kw": float(r.peak_opt_kw)}
                  for d, r in daily.iterrows()]

    base_kwh = float(measured.sum() * step_h)
    opt_kwh = float(optimized.sum() * step_h)
    saving = base_kwh - opt_kwh
    kpi = {
        "baseline_kwh": round(base_kwh, 1), "optimized_kwh": round(opt_kwh, 1),
        "saving_kwh": round(saving, 1),
        "saving_percent": round(100 * saving / base_kwh, 2) if base_kwh else 0.0,
        "cost_saving_vnd": round(float(g.cost_base.sum() - g.cost_opt.sum())),
        "peak_reduction_kw": round(float((peak["base"] - peak["opt"]).mean()), 2),
        "comfort_violation_delta_min": comfort_delta_min,
        "co2_avoided_kg": round(saving * GRID_CO2_KG_PER_KWH, 1),
        "days": len(daily_list),
    }
    return {"policy": {"setpoint_delta_c": setpoint_delta,
                       "peak_window": f"{peak_start:02d}:00-{peak_end:02d}:00",
                       "engine": "zone_surrogate_r2_0.92"},
            "metadata": {"model": loaded.metadata()},
            "kpi": kpi, "daily": daily_list}

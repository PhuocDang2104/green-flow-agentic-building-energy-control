"""Serving for the lag-based next-step forecaster (scripts/train_forecast_lag.py).

Loads the LightGBM booster and rebuilds the SAME features from recent history to
predict t+1; day-ahead = recursive rollout (feed each prediction back as the next
lag). Best-effort: returns None if the model/lightgbm/history is missing so the
caller falls back to the deterministic schedule forecast.

Lag-based on purpose (momentum is the strongest signal for a forecast) — the
opposite of the no-lag what-if surrogate. Never use this for what-if.
"""
from __future__ import annotations

import math
from functools import lru_cache

from .model_registry import load_model
# Must match FEATS order in scripts/train_forecast_lag.py
FEATS = ["cur", "lag1", "lag2", "lag3", "lag_day", "roll_mean", "roll_std",
         "delta", "hour_sin", "hour_cos", "dow", "is_weekend", "occ", "otemp"]
STEPS_PER_DAY = 48


@lru_cache(maxsize=1)
def _booster():
    loaded = load_model("forecast")
    return loaded.model if loaded is not None else None


def available() -> bool:
    return _booster() is not None


def _features(hist: list[float], occ: float, otemp: float, dt) -> list[float]:
    """hist = past total_power oldest..newest, newest = value NOW (cur)."""
    cur = hist[-1]
    lag1 = hist[-2] if len(hist) >= 2 else cur
    lag2 = hist[-3] if len(hist) >= 3 else lag1
    lag3 = hist[-4] if len(hist) >= 4 else lag2
    lag_day = hist[-STEPS_PER_DAY] if len(hist) >= STEPS_PER_DAY else cur
    last4 = hist[-4:]
    mean = sum(last4) / len(last4)
    std = (sum((x - mean) ** 2 for x in last4) / (len(last4) - 1)) ** 0.5 if len(last4) > 1 else 0.0
    h = dt.hour + dt.minute / 60.0
    return [cur, lag1, lag2, lag3, lag_day, mean, std, cur - lag1,
            math.sin(2 * math.pi * h / 24), math.cos(2 * math.pi * h / 24),
            dt.weekday(), int(dt.weekday() >= 5), occ, otemp]


def predict_next(hist: list[float], occ: float, otemp: float, dt) -> float | None:
    """Predict total power at the next 30-min step."""
    b = _booster()
    if b is None or not hist:
        return None
    return float(b.predict([_features(hist, occ, otemp, dt)])[0])


def predict_day_ahead(hist: list[float], exog: list[tuple]) -> list[tuple] | None:
    """Recursive rollout. exog = [(occ, otemp, dt), ...] for each future step;
    returns [(dt, predicted_kw), ...]. Each prediction is appended as the next lag."""
    b = _booster()
    if b is None or not hist:
        return None
    h = list(hist)
    out = []
    for occ, otemp, dt in exog:
        p = float(b.predict([_features(h, occ, otemp, dt)])[0])
        out.append((dt, round(p, 3)))
        h.append(p)
    return out

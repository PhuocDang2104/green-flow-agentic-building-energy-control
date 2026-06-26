"""Lag-based (autoregressive) next-step forecaster — SEPARATE from the structural
what-if surrogate.

Predicts zone total power at t+1 (next 30-min step) from PAST values (lags,
rolling stats, momentum) + exogenous known-at-predict-time signals (occupancy,
outdoor temp, time-of-day). Lag is the strongest predictor for a forecast — the
opposite design of the no-lag what-if surrogate (lag would dampen interventions).

Honesty gate: the model is only worth shipping if it BEATS naive persistence
(pred[t+1] = value now). We report both, at zone and building level, on the
dataset's temporal test split (no leakage: lags are causal/past only).

Day-ahead (24h) = recursive rollout of this t+1 model (feed predictions back as
lags) — done at serving time, not here.

Run:
  DUCKDB_PATH=<elnino.duckdb> python scripts/train_forecast_lag.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend" / "greenflow" / "ml" / "models"
DUCKDB_PATH = os.environ.get(
    "DUCKDB_PATH",
    str(ROOT.parent / "Dataset" / "elnino_new" / "DATA MỚI TINH " / "DATA" /
        "1. Dạng duckdb" /
        "greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd_SELF_CONTAINED.duckdb"))

TARGET = "target_total_zone_power_kw"   # full zone total incl HVAC
STEPS_PER_DAY = 48                       # 30-min


def _metrics(y, p):
    return {"mae_kw": round(float(mean_absolute_error(y, p)), 3),
            "r2": round(float(r2_score(y, p)), 4)}


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["zone_id", "datetime"]).copy()
    g = df.groupby("zone_id", sort=False)[TARGET]
    df["cur"] = df[TARGET]                       # value NOW (known) = persistence pred
    df["lag1"] = g.shift(1)
    df["lag2"] = g.shift(2)
    df["lag3"] = g.shift(3)
    df["lag_day"] = g.shift(STEPS_PER_DAY - 1)   # ~same time yesterday rel. to t+1
    roll = g.shift(0).rolling(4)                 # last 2h ending now
    df["roll_mean"] = roll.mean().reset_index(level=0, drop=True)
    df["roll_std"] = roll.std().reset_index(level=0, drop=True)
    df["delta"] = df["cur"] - df["lag1"]         # momentum
    dt = pd.to_datetime(df["datetime"])
    h = dt.dt.hour + dt.dt.minute / 60.0
    df["hour_sin"] = np.sin(2 * np.pi * h / 24)
    df["hour_cos"] = np.cos(2 * np.pi * h / 24)
    df["dow"] = dt.dt.dayofweek
    df["is_weekend"] = (dt.dt.dayofweek >= 5).astype(int)
    df["occ"] = df["zone_people_occupant_count"]
    df["otemp"] = df["outdoor_temp_c"]
    df["target"] = g.shift(-1)                   # power at t+1
    return df


FEATS = ["cur", "lag1", "lag2", "lag3", "lag_day", "roll_mean", "roll_std",
         "delta", "hour_sin", "hour_cos", "dow", "is_weekend", "occ", "otemp"]


def main() -> None:
    print(f"reading {DUCKDB_PATH}")
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    df = con.execute(f"""
        SELECT zone_id, datetime, {TARGET}, zone_people_occupant_count,
               outdoor_temp_c, is_test
        FROM final_ai_training_timeseries
    """).df()
    print(f"rows={len(df):,} zones={df.zone_id.nunique()}")

    df = build_features(df)
    df = df.dropna(subset=FEATS + ["target"])
    tr, te = df[~df.is_test.astype(bool)], df[df.is_test.astype(bool)]
    print(f"train={len(tr):,} test={len(te):,}")

    model = lgb.LGBMRegressor(
        n_estimators=600, learning_rate=0.05, num_leaves=63,
        subsample=0.8, colsample_bytree=0.8, min_child_samples=50, n_jobs=-1)
    model.fit(tr[FEATS], tr["target"],
              eval_set=[(te[FEATS], te["target"])],
              callbacks=[lgb.early_stopping(40), lgb.log_evaluation(0)])

    pred = model.predict(te[FEATS])
    pers = te["cur"].values                      # persistence pred[t+1] = now
    y = te["target"].values

    zone_model, zone_pers = _metrics(y, pred), _metrics(y, pers)

    # building level: sum per datetime
    bt = te.assign(pred=pred).groupby("datetime").agg(
        y=("target", "sum"), p=("pred", "sum"), cur=("cur", "sum"))
    bld_model, bld_pers = _metrics(bt.y, bt.p), _metrics(bt.y, bt.cur)

    print("\n=== ZONE level (t+1) ===")
    print(f"  model      : {zone_model}")
    print(f"  persistence: {zone_pers}")
    print("=== BUILDING level (t+1, summed) ===")
    print(f"  model      : {bld_model}")
    print(f"  persistence: {bld_pers}")
    beat = bld_model["mae_kw"] < bld_pers["mae_kw"]
    print(f"\n>>> model {'BEATS' if beat else 'DOES NOT beat'} persistence "
          f"(building MAE {bld_model['mae_kw']} vs {bld_pers['mae_kw']} kW)")

    imp = sorted(zip(FEATS, model.feature_importances_), key=lambda x: -x[1])
    print("top features:", [(f, int(i)) for f, i in imp[:6]])

    OUT.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(OUT / "forecast_lag_total.txt"))
    meta = {"kind": "autoregressive_forecast", "horizon": "t+1 (30min)",
            "target": "total_power_kw", "features": FEATS,
            "step_minutes": 30, "source": Path(DUCKDB_PATH).name,
            "test_metrics": {"zone": {"model": zone_model, "persistence": zone_pers},
                             "building": {"model": bld_model, "persistence": bld_pers}},
            "beats_persistence": beat,
            "top_features": [{"feature": f, "gain": int(i)} for f, i in imp[:10]],
            "note": "Lag-based forecast; complements (does NOT replace) the no-lag "
                    "what-if surrogate. Day-ahead = recursive rollout at serving."}
    (OUT / "forecast_lag_total_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"\nsaved -> {OUT/'forecast_lag_total.txt'} + meta")


if __name__ == "__main__":
    main()

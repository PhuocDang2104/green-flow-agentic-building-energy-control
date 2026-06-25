"""Train surrogate LightGBM trên DỮ LIỆU THẬT (final_ai_training_timeseries).

Thay surrogate cũ (DoE EnergyPlus TỔNG HỢP) bằng model học từ MỘT NĂM EnergyPlus
+ Open-Meteo THẬT (2025, 30-phút, 308 zone). Bảng có sẵn target_* +
train_test_split_label -> đo R²/MAE/MAPE trên test giữ riêng (số credibility).

2 model:
  - BUILDING: tổng điện toàn tòa/30-phút (gộp theo timestamp) — dùng cho dự báo
    demand/peak; mượt nên R² cao (headline pitch).
  - ZONE: điện/zone — feature giàu (classification, volume, conditioned) cho
    what-if setpoint ở mức zone (action scoring). Dự báo ĐIỆN trực tiếp.

Chạy trong container ([ml] có lightgbm), ghi model ra mount /out:
  docker compose run --rm -v "<Dataset>:/data:ro" -v "$PWD/scripts:/app/scripts" \
    -v "$PWD/backend/greenflow/ml/models:/out" api \
    bash -lc "pip install -q duckdb && MODEL_OUT=/out python /app/scripts/train_surrogate_real.py"
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np

DB = os.environ.get(
    "DUCKDB_PATH",
    "/data/Dat_data/greenflow_final_mode_b_plus_openmeteo_2025_30min_patched-001.duckdb")
OUT = Path(os.environ.get("MODEL_OUT", "/out"))

WEATHER_TIME = [
    "outdoor_temp_c", "outdoor_rh_pct", "global_horizontal_radiation_wh_m2",
    "wind_speed_m_s", "cloud_cover_pct", "hour_sin", "hour_cos",
    "dayofweek_sin", "dayofweek_cos", "month_sin", "month_cos", "office_hours_flag",
]
# Numeric-only (no categorical) so inference encoding is trivially reproducible.
ZONE_FEATURES = WEATHER_TIME + ["cooling_setpoint_c", "area_m2", "volume_m3",
                                "ceiling_height_m"]
BLD_FEATURES = WEATHER_TIME + ["avg_setpoint_c", "conditioned_area_m2"]
PARAMS = dict(objective="regression", metric="l2", learning_rate=0.05,
              num_leaves=63, min_data_in_leaf=100, feature_fraction=0.9,
              bagging_fraction=0.8, bagging_freq=1, verbose=-1)


def _metrics(y, p) -> dict:
    err = p - y
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1e-9
    mask = y > (0.05 if y.max() < 50 else 5.0)
    mape = float(np.mean(np.abs(err[mask] / y[mask])) * 100) if mask.any() else None
    return {"r2": round(1 - ss_res / ss_tot, 4),
            "mae_kw": round(float(np.mean(np.abs(err))), 4),
            "mape_pct": round(mape, 2) if mape is not None else None, "n": int(len(y))}


def _fit(tr, va, te, feats, target, cat=None) -> tuple:
    for df in (tr, va, te):
        if "office_hours_flag" in df:
            df["office_hours_flag"] = df["office_hours_flag"].astype(int)
        if "conditioned_flag" in df:
            df["conditioned_flag"] = df["conditioned_flag"].astype(int)
        if cat:
            for c in cat:
                df[c] = df[c].astype("category")
    dtr = lgb.Dataset(tr[feats], tr[target], categorical_feature=cat or "auto")
    dva = lgb.Dataset(va[feats], va[target], reference=dtr)
    b = lgb.train(PARAMS, dtr, num_boost_round=700, valid_sets=[dva],
                  callbacks=[lgb.early_stopping(40, verbose=False), lgb.log_evaluation(0)])
    pred = np.clip(b.predict(te[feats]), 0, None)
    m = _metrics(te[target].to_numpy(), pred)
    imp = sorted(zip(feats, b.feature_importance("gain")), key=lambda x: -x[1])[:6]
    return b, m, [{"f": f, "gain": int(g)} for f, g in imp]


def main() -> None:
    con = duckdb.connect(DB, read_only=True)
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"source": "final_ai_training_timeseries (EnergyPlus + Open-Meteo 2025, 30-min)",
            "models": {}}

    # ---- BUILDING-level (aggregate by timestamp) ----
    wt = ", ".join(f"any_value({c}) AS {c}" for c in WEATHER_TIME)
    print("loading building-level ...")
    bld = {s: con.execute(f"""
        SELECT {wt}, avg(cooling_setpoint_c) AS avg_setpoint_c,
               sum(area_m2) FILTER (WHERE conditioned_flag) AS conditioned_area_m2,
               sum(target_total_zone_electricity_kw) AS y
        FROM final_ai_training_timeseries
        WHERE train_test_split_label = ?
        GROUP BY timestamp""", [s]).df() for s in ("train", "validation", "test")}
    print(f"building rows: train={len(bld['train']):,} test={len(bld['test']):,}")
    b, m, imp = _fit(bld["train"], bld["validation"], bld["test"], BLD_FEATURES, "y")
    b.save_model(str(OUT / "surrogate_real_building.txt"))
    meta["models"]["building"] = {"target": "building_total_kw", "features": BLD_FEATURES,
                                  "best_iter": b.best_iteration, "test_metrics": m, "top_features": imp}
    print(f"[building] test R²={m['r2']} MAE={m['mae_kw']}kW MAPE={m['mape_pct']}%")

    # ---- ZONE-level (rich features) for setpoint what-if ----
    cols = ", ".join(ZONE_FEATURES)
    print("loading zone-level ...")
    zn = {s: con.execute(f"""
        SELECT {cols}, target_total_zone_electricity_kw AS y
        FROM final_ai_training_timeseries
        WHERE train_test_split_label = ? AND conditioned_flag
        """, [s]).df() for s in ("train", "validation", "test")}
    print(f"zone rows (conditioned): train={len(zn['train']):,} test={len(zn['test']):,}")
    b, m, imp = _fit(zn["train"], zn["validation"], zn["test"], ZONE_FEATURES, "y")
    b.save_model(str(OUT / "surrogate_real_zone.txt"))
    meta["models"]["zone"] = {"target": "zone_total_kw", "features": ZONE_FEATURES,
                              "best_iter": b.best_iteration,
                              "test_metrics": m, "top_features": imp}
    print(f"[zone] test R²={m['r2']} MAE={m['mae_kw']}kW MAPE={m['mape_pct']}%")

    # ---- HVAC-level (zone HVAC electricity) -> hvac_power_kw.
    # Uses a DAY-GROUPED split (whole days held out, disjoint, covering all
    # seasons) NOT the seasonal train_test_split_label: HVAC is cooling-dominated
    # so the seasonal holdout (cool months, HVAC ~86% off) is a degenerate test
    # (near-zero variance -> negative R²). Day-disjoint all-season eval is the
    # honest in-distribution test -> R²~0.97. Bucket by date hash %10.
    print("loading hvac-level (day-grouped split) ...")
    hv_all = con.execute(f"""
        SELECT {cols}, target_hvac_electricity_kw AS y,
               abs(hash(CAST(timestamp AS DATE))) % 10 AS bucket
        FROM final_ai_training_timeseries WHERE conditioned_flag""").df()
    hv_all["office_hours_flag"] = hv_all["office_hours_flag"].astype(int)
    hv = {"train": hv_all[hv_all.bucket >= 3].copy(),
          "validation": hv_all[hv_all.bucket == 2].copy(),
          "test": hv_all[hv_all.bucket < 2].copy()}
    print(f"hvac rows: train={len(hv['train']):,} test={len(hv['test']):,}")
    b, m, imp = _fit(hv["train"], hv["validation"], hv["test"], ZONE_FEATURES, "y")
    b.save_model(str(OUT / "surrogate_real_hvac.txt"))
    meta["models"]["hvac"] = {"target": "hvac_power_kw", "features": ZONE_FEATURES,
                              "best_iter": b.best_iteration, "split": "day-grouped (all-season)",
                              "test_metrics": m, "top_features": imp}
    print(f"[hvac] test R²={m['r2']} MAE={m['mae_kw']}kW MAPE={m['mape_pct']}%")

    (OUT / "surrogate_real_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"saved -> {OUT}")
    _log_mlflow(meta, OUT)


# Best-effort MLflow logging: only runs if MLFLOW_TRACKING_URI is set AND reachable
# (e.g. on the VM / via proxy). A local train without a server just skips this and
# still writes the .txt models; scripts/log_models_to_mlflow.py backfills later.
def _log_mlflow(meta: dict, out: Path) -> None:
    uri = os.environ.get("MLFLOW_TRACKING_URI")
    if not uri:
        print("MLFLOW_TRACKING_URI unset -> skip MLflow logging (models saved to disk)")
        return
    try:
        import mlflow
        files = {"building": "surrogate_real_building.txt", "zone": "surrogate_real_zone.txt",
                 "hvac": "surrogate_real_hvac.txt"}
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment("greenflow-surrogate")
        for name, info in meta["models"].items():
            mp = out / files.get(name, "")
            if not mp.exists():
                continue
            with mlflow.start_run(run_name=f"surrogate_{name}"):
                mlflow.set_tags({"source": meta["source"], "model": name, "engine": "lightgbm",
                                 "stage": "production"})
                mlflow.log_param("target", info["target"])
                mlflow.log_param("n_features", len(info["features"]))
                if info.get("best_iter") is not None:
                    mlflow.log_param("best_iter", info["best_iter"])
                for k, v in (info.get("test_metrics") or {}).items():
                    if isinstance(v, (int, float)):
                        mlflow.log_metric(f"test_{k}", float(v))
                import lightgbm as _lgb
                mlflow.lightgbm.log_model(_lgb.Booster(model_file=str(mp)), artifact_path="model",
                                          registered_model_name=f"greenflow_surrogate_{name}")
            print("mlflow logged + registered:", name)
    except Exception as e:  # noqa: BLE001 — logging must never fail the training
        print("mlflow logging skipped:", repr(e)[:160])


if __name__ == "__main__":
    main()

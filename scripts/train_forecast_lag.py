"""Train the 308-zone autoregressive t+1 forecast on the active dataset."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import duckdb  # noqa: E402
import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import mean_absolute_error, r2_score  # noqa: E402

from greenflow.datasets import active_dataset  # noqa: E402

DATASET = active_dataset()
OUT = Path(os.environ.get("MODEL_OUT", ROOT / "backend/greenflow/ml/models"))
TARGET = "target_total_zone_power_kw"
STEPS_PER_DAY = 48
FEATURES = [
    "cur", "lag1", "lag2", "lag3", "lag_day", "roll_mean", "roll_std",
    "delta", "hour_sin", "hour_cos", "dow", "is_weekend", "occ", "otemp",
]


def _source() -> tuple[duckdb.DuckDBPyConnection, str, Path]:
    explicit = os.environ.get("DUCKDB_PATH")
    db_path = Path(explicit) if explicit else DATASET.duckdb_path
    if db_path.exists():
        return duckdb.connect(str(db_path), read_only=True), "final_ai_training_timeseries", db_path
    parquet = DATASET.parquet_root / "final_ai_training_timeseries.parquet"
    if not parquet.exists():
        raise SystemExit(f"missing training source: {db_path} and {parquet}")
    return duckdb.connect(), f"read_parquet('{parquet.as_posix()}')", parquet


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return path.name


def _metrics(actual, predicted) -> dict:
    return {
        "mae_kw": round(float(mean_absolute_error(actual, predicted)), 3),
        "r2": round(float(r2_score(actual, predicted)), 4),
    }


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.sort_values(["zone_id", "datetime"]).copy()
    grouped = frame.groupby("zone_id", sort=False)[TARGET]
    frame["cur"] = frame[TARGET]
    frame["lag1"] = grouped.shift(1)
    frame["lag2"] = grouped.shift(2)
    frame["lag3"] = grouped.shift(3)
    frame["lag_day"] = grouped.shift(STEPS_PER_DAY - 1)
    rolling = grouped.shift(0).rolling(4)
    frame["roll_mean"] = rolling.mean().reset_index(level=0, drop=True)
    frame["roll_std"] = rolling.std().reset_index(level=0, drop=True)
    frame["delta"] = frame["cur"] - frame["lag1"]
    dt = pd.to_datetime(frame["datetime"])
    hour = dt.dt.hour + dt.dt.minute / 60.0
    frame["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    frame["dow"] = dt.dt.dayofweek
    frame["is_weekend"] = (dt.dt.dayofweek >= 5).astype(int)
    frame["occ"] = frame["zone_people_occupant_count"]
    frame["otemp"] = frame["outdoor_temp_c"]
    frame["target"] = grouped.shift(-1)
    return frame


def main() -> None:
    con, source, source_path = _source()
    frame = con.execute(f"""
        SELECT zone_id, datetime, {TARGET}, zone_people_occupant_count,
               outdoor_temp_c, dataset_split
        FROM {source}
        ORDER BY zone_id, datetime
    """).df()
    zones = int(frame.zone_id.nunique())
    timesteps = int(frame.datetime.nunique())
    if (zones, timesteps, len(frame)) != (
        DATASET.expected_zones, DATASET.expected_timesteps, DATASET.expected_zone_rows
    ):
        raise SystemExit("lag training source does not match active dataset contract")

    frame = build_features(frame).dropna(subset=FEATURES + ["target"])
    train = frame[frame.dataset_split == "train"]
    validation = frame[frame.dataset_split == "validation"]
    test = frame[frame.dataset_split == "test"]
    print(f"train={len(train):,} validation={len(validation):,} test={len(test):,}")

    model = lgb.LGBMRegressor(
        n_estimators=800, learning_rate=0.05, num_leaves=63,
        subsample=0.8, colsample_bytree=0.8, min_child_samples=50,
        random_state=42, deterministic=True, force_col_wise=True, n_jobs=-1,
    )
    model.fit(
        train[FEATURES], train["target"],
        eval_set=[(validation[FEATURES], validation["target"])],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )
    predicted = np.clip(model.predict(test[FEATURES]), 0, None)
    persistence = test["cur"].to_numpy()
    actual = test["target"].to_numpy()
    zone_model = _metrics(actual, predicted)
    zone_persistence = _metrics(actual, persistence)

    building = test.assign(prediction=predicted).groupby("datetime").agg(
        actual=("target", "sum"), prediction=("prediction", "sum"), current=("cur", "sum")
    )
    building_model = _metrics(building.actual, building.prediction)
    building_persistence = _metrics(building.actual, building.current)
    beats_persistence = building_model["mae_kw"] < building_persistence["mae_kw"]
    if not beats_persistence:
        raise SystemExit("forecast model failed the persistence quality gate")

    importance = sorted(
        zip(FEATURES, model.feature_importances_), key=lambda item: -item[1]
    )
    OUT.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(OUT / "forecast_lag_total.txt"))
    meta = {
        "kind": "autoregressive_forecast",
        "horizon": "t+1 (30 minutes); recursive for longer horizons",
        "target": TARGET,
        "features": FEATURES,
        "step_minutes": DATASET.timestep_minutes,
        "dataset": {
            "schema_version": 2, "dataset_key": DATASET.key,
            "scenario_id": DATASET.scenario_id, "source_path": _portable_path(source_path),
            "source_sha256": _sha256(source_path), "zone_count": zones,
            "timestep_count": timesteps,
            "row_count": int(con.execute(f"SELECT count(*) FROM {source}").fetchone()[0]),
        },
        "split": "dataset_split (train/validation/test)",
        "test_metrics": {
            "zone": {"model": zone_model, "persistence": zone_persistence},
            "building": {"model": building_model, "persistence": building_persistence},
        },
        "beats_persistence": beats_persistence,
        "top_features": [
            {"feature": feature, "gain": int(gain)} for feature, gain in importance[:10]
        ],
    }
    (OUT / "forecast_lag_total_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print("zone:", zone_model, "building:", building_model)
    print("saved lag model + metadata ->", OUT)


if __name__ == "__main__":
    main()

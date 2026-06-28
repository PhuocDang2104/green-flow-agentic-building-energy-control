"""Train the production surrogates on the active 308-zone data contract.

Targets and splits intentionally match ``final_ai_training_timeseries`` from
the El Nino Mar-Apr 2024 package:

* building: ``target_facility_power_kw`` (one facility-meter value/timestep)
* zone: ``target_total_zone_power_kw``
* HVAC: ``target_hvac_power_kw``
* split: ``dataset_split`` = train / validation / test

The script writes reproducible LightGBM text artifacts plus a metadata contract
containing the dataset fingerprint, coverage, targets, features and test scores.
"""

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

from greenflow.datasets import active_dataset  # noqa: E402

DATASET = active_dataset()
OUT = Path(os.environ.get("MODEL_OUT", ROOT / "backend/greenflow/ml/models"))

WEATHER_TIME = [
    "outdoor_temp_c", "outdoor_rh_pct", "global_horizontal_radiation_wh_m2",
    "wind_speed_m_s", "cloud_cover_pct", "hour_sin", "hour_cos",
    "dayofweek_sin", "dayofweek_cos", "month_sin", "month_cos", "office_hours_flag",
]
WEATHER_EXPRESSIONS = {
    "outdoor_temp_c": "outdoor_temp_c",
    "outdoor_rh_pct": "outdoor_rh_pct",
    "global_horizontal_radiation_wh_m2": "global_horizontal_radiation_wh_m2",
    "wind_speed_m_s": "wind_speed_m_s",
    "cloud_cover_pct": "coalesce(total_sky_cover_tenths, 4) * 10",
    "hour_sin": "sin(2 * pi() * hour_decimal / 24)",
    "hour_cos": "cos(2 * pi() * hour_decimal / 24)",
    "dayofweek_sin": "sin(2 * pi() * dayofweek / 7)",
    "dayofweek_cos": "cos(2 * pi() * dayofweek / 7)",
    "month_sin": "sin(2 * pi() * month / 12)",
    "month_cos": "cos(2 * pi() * month / 12)",
    "office_hours_flag": "CASE WHEN dayofweek < 5 AND hour_decimal >= 7 "
                         "AND hour_decimal < 19 THEN 1 ELSE 0 END",
}
ZONE_FEATURES = WEATHER_TIME + [
    "cooling_setpoint_c", "area_m2_final", "volume_m3_final", "height_m_final",
]
BUILDING_FEATURES = WEATHER_TIME + ["avg_setpoint_c", "detailed_area_m2"]
PARAMS = {
    "objective": "regression", "metric": "l2", "learning_rate": 0.05,
    "num_leaves": 63, "min_data_in_leaf": 100, "feature_fraction": 0.9,
    "bagging_fraction": 0.8, "bagging_freq": 1, "verbose": -1,
    "seed": 42, "feature_fraction_seed": 42, "bagging_seed": 42,
    "deterministic": True, "force_col_wise": True,
}


def _source() -> tuple[duckdb.DuckDBPyConnection, str, Path]:
    explicit = os.environ.get("DUCKDB_PATH")
    db_path = Path(explicit) if explicit else DATASET.duckdb_path
    if db_path.exists():
        return duckdb.connect(str(db_path), read_only=True), "final_ai_training_timeseries", db_path
    parquet = DATASET.parquet_root / "final_ai_training_timeseries.parquet"
    if not parquet.exists():
        raise SystemExit(f"missing training source: {db_path} and {parquet}")
    con = duckdb.connect()
    return con, f"read_parquet('{parquet.as_posix()}')", parquet


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


def _metrics(y, pred) -> dict:
    err = pred - y
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1e-9
    threshold = 5.0 if float(np.max(y)) >= 50 else 0.05
    mask = y > threshold
    mape = float(np.mean(np.abs(err[mask] / y[mask])) * 100) if mask.any() else None
    return {
        "r2": round(1 - ss_res / ss_tot, 4),
        "mae_kw": round(float(np.mean(np.abs(err))), 4),
        "mape_pct": round(mape, 2) if mape is not None else None,
        "n": int(len(y)),
    }


def _fit(frames: dict, features: list[str], target: str) -> tuple:
    train, validation, test = (frames[key].copy() for key in ("train", "validation", "test"))
    for frame in (train, validation, test):
        frame["office_hours_flag"] = frame["office_hours_flag"].astype(int)
    dtrain = lgb.Dataset(train[features], train[target])
    dvalid = lgb.Dataset(validation[features], validation[target], reference=dtrain)
    booster = lgb.train(
        PARAMS, dtrain, num_boost_round=800, valid_sets=[dvalid],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )
    pred = np.clip(booster.predict(test[features]), 0, None)
    metrics = _metrics(test[target].to_numpy(), pred)
    importance = sorted(
        zip(features, booster.feature_importance("gain")), key=lambda item: -item[1]
    )[:10]
    return booster, metrics, [{"f": feature, "gain": int(gain)} for feature, gain in importance]


def _dataset_contract(con, source: str, source_path: Path) -> dict:
    columns = {row[0] for row in con.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()}
    required = {
        "datetime", "zone_id", "dataset_split", "room_type",
        "outdoor_temp_c", "outdoor_rh_pct", "global_horizontal_radiation_wh_m2",
        "wind_speed_m_s", "total_sky_cover_tenths", "hour_decimal", "dayofweek", "month",
        "cooling_setpoint_c", "area_m2_final", "volume_m3_final", "height_m_final",
        "target_facility_power_kw", "target_total_zone_power_kw", "target_hvac_power_kw",
    }
    missing = sorted(required - columns)
    if missing:
        raise SystemExit(f"training source violates v2 contract; missing columns: {missing}")
    row = con.execute(f"""
        SELECT count(*) AS rows, count(DISTINCT zone_id) AS zones,
               count(DISTINCT datetime) AS timesteps, min(datetime), max(datetime)
        FROM {source}
    """).fetchone()
    splits = {
        split: {"rows": int(rows), "timesteps": int(timesteps), "zones": int(zones)}
        for split, rows, timesteps, zones in con.execute(f"""
            SELECT dataset_split, count(*), count(DISTINCT datetime), count(DISTINCT zone_id)
            FROM {source} GROUP BY dataset_split ORDER BY dataset_split
        """).fetchall()
    }
    contract = {
        "schema_version": 2,
        "dataset_key": DATASET.key,
        "scenario_id": DATASET.scenario_id,
        "timezone": DATASET.timezone,
        "timestep_minutes": DATASET.timestep_minutes,
        "source_path": _portable_path(source_path),
        "source_sha256": _sha256(source_path),
        "zone_count": int(row[1]),
        "timestep_count": int(row[2]),
        "row_count": int(row[0]),
        "time_range": {"start": str(row[3]), "end": str(row[4])},
        "splits": splits,
    }
    expected = (DATASET.expected_zones, DATASET.expected_timesteps, DATASET.expected_zone_rows)
    actual = (contract["zone_count"], contract["timestep_count"], contract["row_count"])
    if actual != expected:
        raise SystemExit(f"dataset coverage mismatch: expected={expected}, actual={actual}")
    return contract


def main() -> None:
    con, source, source_path = _source()
    contract = _dataset_contract(con, source, source_path)
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {
        "source": f"{DATASET.key} · EnergyPlus facility/zone targets · 30-minute",
        "dataset": contract,
        "models": {},
    }
    print("dataset contract:", json.dumps(contract, indent=2))

    weather = ", ".join(
        f"any_value({WEATHER_EXPRESSIONS[column]}) AS {column}" for column in WEATHER_TIME
    )
    print("loading building model frames ...")
    building_frames = {
        split: con.execute(f"""
            SELECT {weather}, avg(cooling_setpoint_c) AS avg_setpoint_c,
                   sum(area_m2_final) FILTER (WHERE room_type <> 'gross_area_placeholder')
                       AS detailed_area_m2,
                   any_value(target_facility_power_kw) AS target
            FROM {source}
            WHERE dataset_split = ?
            GROUP BY datetime ORDER BY datetime
        """, [split]).df()
        for split in ("train", "validation", "test")
    }
    model, metrics, importance = _fit(building_frames, BUILDING_FEATURES, "target")
    model.save_model(str(OUT / "surrogate_real_building.txt"))
    meta["models"]["building"] = {
        "target": "target_facility_power_kw", "features": BUILDING_FEATURES,
        "best_iter": model.best_iteration, "split": "dataset_split",
        "test_metrics": metrics, "top_features": importance,
    }
    print("[building]", metrics)

    columns = ", ".join(
        [f"{WEATHER_EXPRESSIONS[column]} AS {column}" for column in WEATHER_TIME]
        + ["cooling_setpoint_c", "area_m2_final", "volume_m3_final", "height_m_final"]
    )
    for kind, target, filename in (
        ("zone", "target_total_zone_power_kw", "surrogate_real_zone.txt"),
        ("hvac", "target_hvac_power_kw", "surrogate_real_hvac.txt"),
    ):
        print(f"loading {kind} model frames ...")
        frames = {
            split: con.execute(f"""
                SELECT {columns}, {target} AS target
                FROM {source}
                WHERE dataset_split = ?
                ORDER BY zone_id, datetime
            """, [split]).df()
            for split in ("train", "validation", "test")
        }
        model, metrics, importance = _fit(frames, ZONE_FEATURES, "target")
        model.save_model(str(OUT / filename))
        meta["models"][kind] = {
            "target": target, "features": ZONE_FEATURES,
            "best_iter": model.best_iteration, "split": "dataset_split",
            "test_metrics": metrics, "top_features": importance,
        }
        print(f"[{kind}]", metrics)

    metadata_path = OUT / "surrogate_real_meta.json"
    metadata_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("saved models + metadata ->", OUT)


if __name__ == "__main__":
    main()

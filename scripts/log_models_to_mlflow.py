"""Register dataset-aligned models in MLflow and advance the production aliases."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import lightgbm as lgb
import mlflow

TRACKING = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MODELS = Path(__file__).resolve().parents[1] / "backend/greenflow/ml/models"
FILES = {
    "building": MODELS / "surrogate_real_building.txt",
    "zone": MODELS / "surrogate_real_zone.txt",
    "hvac": MODELS / "surrogate_real_hvac.txt",
    "forecast": MODELS / "forecast_lag_total.txt",
}
REGISTERED = {
    "building": "greenflow_surrogate_building",
    "zone": "greenflow_surrogate_zone",
    "hvac": "greenflow_surrogate_hvac",
    "forecast": "greenflow_forecast_lag_total",
}


def _flatten_metrics(value, prefix=""):
    for key, item in value.items():
        name = f"{prefix}_{key}" if prefix else key
        if isinstance(item, dict):
            yield from _flatten_metrics(item, name)
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            yield name, float(item)


def _specs() -> dict:
    surrogate = json.loads((MODELS / "surrogate_real_meta.json").read_text())
    lag = json.loads((MODELS / "forecast_lag_total_meta.json").read_text())
    specs = {
        name: {**info, "dataset": surrogate["dataset"], "source": surrogate["source"]}
        for name, info in surrogate["models"].items()
    }
    specs["forecast"] = {**lag, "source": lag["dataset"]["dataset_key"]}
    return specs


def main() -> None:
    mlflow.set_tracking_uri(TRACKING)
    mlflow.set_experiment("greenflow-surrogate")
    client = mlflow.MlflowClient()
    only = set(sys.argv[1:])

    for name, info in _specs().items():
        if only and name not in only:
            continue
        model_file = FILES[name]
        dataset = info["dataset"]
        registered_name = REGISTERED[name]
        booster = lgb.Booster(model_file=str(model_file))
        with mlflow.start_run(run_name=f"{name}_{dataset['dataset_key']}") as run:
            mlflow.set_tags({
                "source": info.get("source", ""), "stage": "production",
                "model": name, "engine": "lightgbm",
                "dataset_key": dataset["dataset_key"],
                "dataset_sha256": dataset["source_sha256"],
            })
            mlflow.log_params({
                "target": info["target"], "n_features": len(info["features"]),
                "features": ",".join(info["features"]),
                "zone_count": dataset["zone_count"],
                "timestep_count": dataset["timestep_count"],
                "row_count": dataset["row_count"],
                "split": info.get("split", "dataset_split"),
            })
            if info.get("best_iter") is not None:
                mlflow.log_param("best_iter", info["best_iter"])
            for metric, value in _flatten_metrics(info.get("test_metrics", {}), "test"):
                mlflow.log_metric(metric, value)
            for feature in (info.get("top_features") or [])[:10]:
                key = feature.get("f") or feature.get("feature")
                mlflow.log_metric(f"gain__{key}", float(feature["gain"]))
            mlflow.lightgbm.log_model(
                booster, artifact_path="model", registered_model_name=registered_name
            )

        versions = client.search_model_versions(f"name = '{registered_name}'")
        version = next(version for version in versions if version.run_id == run.info.run_id)
        client.set_registered_model_alias(registered_name, "production", version.version)
        print(
            "registered", registered_name, "version", version.version,
            "alias=production", "dataset", dataset["dataset_key"],
        )


if __name__ == "__main__":
    main()

"""Backfill the trained surrogate models into MLflow (tracking + model registry).

Reads the committed LightGBM models + their held-out test metrics (meta json) and
logs them as MLflow runs, then registers each in the Model Registry. This makes
the registry reflect the REAL production models WITHOUT needing the 3.8 GB
training dataset (which lives offline). Run inside the api container so it reaches
the mlflow server on the internal docker network:

  docker compose exec -T api sh -c \
    "pip install -q mlflow && MLFLOW_TRACKING_URI=http://mlflow:5000 \
     python /app/scripts/log_models_to_mlflow.py"
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import lightgbm as lgb
import mlflow

TRACKING = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MODELS = Path(__file__).resolve().parents[1] / "backend" / "greenflow" / "ml" / "models"
FILES = {
    "building": MODELS / "surrogate_real_building.txt",
    "zone": MODELS / "surrogate_real_zone.txt",
}


def main() -> None:
    mlflow.set_tracking_uri(TRACKING)
    mlflow.set_experiment("greenflow-surrogate")
    meta = json.loads((MODELS / "surrogate_real_meta.json").read_text())

    for name, info in meta["models"].items():
        f = FILES.get(name)
        if not f or not f.exists():
            print("skip", name, "(no model file)")
            continue
        booster = lgb.Booster(model_file=str(f))
        with mlflow.start_run(run_name=f"surrogate_{name}"):
            mlflow.set_tags({"source": meta.get("source", ""), "stage": "production",
                             "model": name, "engine": "lightgbm"})
            mlflow.log_param("target", info["target"])
            mlflow.log_param("n_features", len(info["features"]))
            mlflow.log_param("features", ",".join(info["features"]))
            if info.get("best_iter") is not None:
                mlflow.log_param("best_iter", info["best_iter"])
            for k, v in (info.get("test_metrics") or {}).items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(f"test_{k}", float(v))
            for tf in (info.get("top_features") or [])[:10]:
                mlflow.log_metric(f"gain__{tf['f']}", float(tf["gain"]))
            mlflow.lightgbm.log_model(booster, artifact_path="model",
                                      registered_model_name=f"greenflow_surrogate_{name}")
        print("logged + registered:", f"greenflow_surrogate_{name}",
              "| test_metrics:", info.get("test_metrics"))


if __name__ == "__main__":
    main()

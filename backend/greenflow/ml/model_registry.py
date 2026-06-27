"""Runtime model provider for GreenFlow surrogate models.

MLflow Registry is the preferred source in production. The committed LightGBM
text models under ``ml/models`` remain an offline fallback so local development
and tests do not require a running MLflow server.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import get_settings

MODEL_DIR = Path(__file__).resolve().parent / "models"

MODEL_FILES = {
    "building": "surrogate_real_building.txt",
    "zone": "surrogate_real_zone.txt",
    "hvac": "surrogate_real_hvac.txt",
}

REGISTERED_MODELS = {
    "building": "greenflow_surrogate_building",
    "zone": "greenflow_surrogate_zone",
    "hvac": "greenflow_surrogate_hvac",
}


@dataclass(frozen=True)
class LoadedModel:
    key: str
    model: Any
    features: list[str]
    source: str
    registered_model: str
    model_uri: str
    version: str | None = None
    run_id: str | None = None
    error: str | None = None

    def metadata(self) -> dict:
        return {
            "key": self.key,
            "source": self.source,
            "registered_model": self.registered_model,
            "model_uri": self.model_uri,
            "version": self.version,
            "run_id": self.run_id,
            "n_features": len(self.features),
            "error": self.error,
        }


def _meta() -> dict:
    try:
        return json.loads((MODEL_DIR / "surrogate_real_meta.json").read_text())
    except Exception:
        return {"models": {}}


def model_metrics() -> dict:
    return _meta().get("models", {})


def _features(kind: str) -> list[str]:
    return list((_meta().get("models", {}).get(kind, {}) or {}).get("features", []))


def _configured_uri(kind: str) -> str:
    s = get_settings()
    return {
        "building": s.greenflow_model_building,
        "zone": s.greenflow_model_zone,
        "hvac": s.greenflow_model_hvac,
    }.get(kind, f"models:/{REGISTERED_MODELS[kind]}/1")


def _parse_model_uri(kind: str, uri: str) -> tuple[str | None, str | None]:
    registered = REGISTERED_MODELS.get(kind)
    version = None
    # Supports models:/name/1 and models:/name@production. Alias resolution is
    # left to MLflow; we only expose the configured selector as metadata.
    if uri.startswith("models:/"):
        tail = uri[len("models:/"):]
        if "@" in tail:
            registered, version = tail.split("@", 1)
        elif "/" in tail:
            registered, version = tail.rsplit("/", 1)
        else:
            registered = tail
    return registered, version


def _load_mlflow(kind: str) -> LoadedModel | None:
    uri = _configured_uri(kind)
    registered, version = _parse_model_uri(kind, uri)
    try:
        import mlflow

        mlflow.set_tracking_uri(get_settings().mlflow_tracking_uri)
        try:
            import mlflow.lightgbm
            model = mlflow.lightgbm.load_model(uri)
        except Exception:
            model = mlflow.pyfunc.load_model(uri)
        return LoadedModel(
            key=kind,
            model=model,
            features=_features(kind),
            source="mlflow",
            registered_model=registered or REGISTERED_MODELS[kind],
            model_uri=uri,
            version=version,
        )
    except Exception as exc:  # noqa: BLE001 - fallback handles registry outages
        return LoadedModel(
            key=kind,
            model=None,
            features=_features(kind),
            source="mlflow_unavailable",
            registered_model=registered or REGISTERED_MODELS[kind],
            model_uri=uri,
            version=version,
            error=repr(exc)[:240],
        )


def _load_local(kind: str, *, previous_error: str | None = None) -> LoadedModel | None:
    try:
        import lightgbm as lgb

        model = lgb.Booster(model_file=str(MODEL_DIR / MODEL_FILES[kind]))
        return LoadedModel(
            key=kind,
            model=model,
            features=_features(kind),
            source="local_file",
            registered_model=REGISTERED_MODELS[kind],
            model_uri=str(MODEL_DIR / MODEL_FILES[kind]),
            error=previous_error,
        )
    except Exception as exc:  # noqa: BLE001
        err = previous_error or repr(exc)[:240]
        return LoadedModel(
            key=kind,
            model=None,
            features=_features(kind),
            source="unavailable",
            registered_model=REGISTERED_MODELS[kind],
            model_uri=str(MODEL_DIR / MODEL_FILES.get(kind, "")),
            error=err,
        )


@lru_cache(maxsize=8)
def load_model(kind: str) -> LoadedModel | None:
    if kind not in REGISTERED_MODELS:
        raise ValueError(f"unknown surrogate model kind: {kind}")
    source = (get_settings().greenflow_model_source or "mlflow").lower()
    if source == "local":
        local = _load_local(kind)
        return local
    mlflow_model = _load_mlflow(kind)
    if mlflow_model and mlflow_model.model is not None:
        return mlflow_model
    local = _load_local(kind, previous_error=mlflow_model.error if mlflow_model else None)
    return local


def model_inventory() -> list[dict]:
    metrics = model_metrics()
    out = []
    for kind, registered in REGISTERED_MODELS.items():
        loaded = load_model(kind)
        info = metrics.get(kind, {})
        meta = loaded.metadata() if loaded else {
            "key": kind,
            "source": "unavailable",
            "registered_model": registered,
            "model_uri": _configured_uri(kind),
            "version": None,
            "run_id": None,
            "n_features": len(_features(kind)),
            "error": "model not loadable",
        }
        meta.update({
            "target": info.get("target"),
            "metrics": info.get("test_metrics", {}),
            "split": info.get("split", "seasonal holdout (cool months)"),
            "top_features": [t["f"] for t in (info.get("top_features") or [])[:5]],
        })
        out.append(meta)
    return out

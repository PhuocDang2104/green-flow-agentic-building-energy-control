"""Production ML artifacts must match the active 308-zone data contract."""

import json
from pathlib import Path

from greenflow.config import get_settings
from greenflow.datasets import active_dataset
from greenflow.ml.forecast_service import ROOM_TYPE_TO_ARCHE

MODEL_DIR = Path(__file__).resolve().parents[1] / "greenflow/ml/models"


def test_model_artifacts_share_active_dataset_fingerprint():
    surrogate = json.loads((MODEL_DIR / "surrogate_real_meta.json").read_text())
    forecast = json.loads((MODEL_DIR / "forecast_lag_total_meta.json").read_text())
    contracts = [surrogate["dataset"], forecast["dataset"]]
    dataset = active_dataset()

    assert all(contract["dataset_key"] == dataset.key for contract in contracts)
    assert all(contract["zone_count"] == dataset.expected_zones for contract in contracts)
    assert all(contract["row_count"] == dataset.expected_zone_rows for contract in contracts)
    assert len({contract["source_sha256"] for contract in contracts}) == 1


def test_forecast_passes_persistence_gate():
    forecast = json.loads((MODEL_DIR / "forecast_lag_total_meta.json").read_text())
    assert forecast["beats_persistence"] is True
    model = forecast["test_metrics"]["building"]["model"]
    persistence = forecast["test_metrics"]["building"]["persistence"]
    assert model["mae_kw"] < persistence["mae_kw"]


def test_all_new_room_types_have_explicit_archetypes():
    room_types = {
        "workspace", "meeting_event", "amenity", "circulation", "parking_shelter",
        "service", "technical_core", "gross_area_placeholder", "unknown",
    }
    assert room_types <= set(ROOM_TYPE_TO_ARCHE)


def test_contracted_demand_is_calibrated_for_full_building():
    assert get_settings().greenflow_contracted_demand_kw == 1000.0

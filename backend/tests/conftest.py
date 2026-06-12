import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

IDF_PATH = ROOT / "data" / "greenflow_archetype.idf"
SEED_FILE = ROOT / "db" / "seed" / "normalized_building.json"


@pytest.fixture(scope="session")
def idf_model():
    from greenflow.bim.idf_parser import parse_idf
    return parse_idf(IDF_PATH)


@pytest.fixture(scope="session")
def normalized(idf_model):
    from greenflow.bim.normalized import build_normalized
    return build_normalized(idf_model)

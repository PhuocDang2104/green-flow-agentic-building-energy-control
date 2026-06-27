"""Dataset configuration shared by telemetry, simulation and electrical layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .config import PROJECT_ROOT, get_settings


@dataclass(frozen=True)
class DatasetConfig:
    key: str
    scenario_id: str
    timezone: str
    timestep_minutes: int
    duckdb_path: Path
    parquet_root: Path
    expected_zones: int
    expected_timesteps: int
    expected_zone_rows: int
    electrical_out: Path

    def to_metadata(self) -> dict:
        data = asdict(self)
        for key in ("duckdb_path", "parquet_root", "electrical_out"):
            data[key] = str(data[key])
        return data


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _default_elnino_duckdb() -> Path:
    root = PROJECT_ROOT / "data" / "final_elnino"
    try:
        return next(root.rglob("*.duckdb"))
    except StopIteration:
        return root / "greenflow_final_mode_b_plus_mar_apr_2024_lpd_epd_SELF_CONTAINED.duckdb"


def _default_elnino_parquet() -> Path:
    root = PROJECT_ROOT / "data" / "final_elnino"
    try:
        return next(root.rglob("final_zone_metadata.parquet")).parent
    except StopIteration:
        return root / "parquet"


def active_dataset() -> DatasetConfig:
    s = get_settings()
    duckdb = _resolve(s.greenflow_duckdb_path) if s.greenflow_duckdb_path else _default_elnino_duckdb()
    parquet = (_resolve(s.greenflow_parquet_root)
               if s.greenflow_parquet_root else _default_elnino_parquet())
    return DatasetConfig(
        key=s.greenflow_dataset,
        scenario_id=s.greenflow_scenario_id,
        timezone=s.greenflow_timezone,
        timestep_minutes=int(s.greenflow_timestep_minutes),
        duckdb_path=duckdb,
        parquet_root=parquet,
        expected_zones=int(s.greenflow_expected_zones),
        expected_timesteps=int(s.greenflow_expected_timesteps),
        expected_zone_rows=int(s.greenflow_expected_zone_rows),
        electrical_out=_resolve(s.greenflow_electrical_out),
    )


def dataset_metadata() -> dict:
    return active_dataset().to_metadata()

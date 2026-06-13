"""Application settings loaded from environment / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+psycopg://greenflow:greenflow@localhost:5432/greenflow"

    llm_provider: str = "groq"  # groq | openai | openrouter | together | ollama
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # AI chat: provider mặc định khi DB chưa cấu hình
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    # mã hoá key provider lưu DB (ĐỔI ở production; KHÔNG commit)
    llm_keystore_secret: str = "change-me-in-production"
    # embedder English: bge-small(384,mặc định) | bge-base | mxbai-large | hashing(dev)
    llm_embedder: str = "bge-small"

    storage_dir: str = "./storage"
    energyplus_bin: str = ""
    weather_epw: str = "./storage/raw/weather/hanoi.epw"
    idf_path: str = "./data/greenflow_archetype.idf"

    enable_auto_actions: bool = True
    max_setpoint_delta_c: float = 1.5
    min_occupancy_confidence: float = 0.8

    default_building_id: str = "b0000000-0000-0000-0000-000000000001"
    replay_speed_seconds: int = 10

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_dir)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def idf_file(self) -> Path:
        p = Path(self.idf_path)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def vector_index_path(self) -> Path:
        return self.storage_path / "processed" / "vector" / "kb.tvim"


@lru_cache
def get_settings() -> Settings:
    return Settings()

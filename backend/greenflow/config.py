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
    # Agent text polishing (action reasons, report prose) via the shared
    # ModelRouter. OFF by default -> agent runs stay fast + fully deterministic.
    agent_llm_polish: bool = False

    # AI chat: provider mặc định khi DB chưa cấu hình
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    # mã hoá key provider lưu DB (ĐỔI ở production; KHÔNG commit)
    llm_keystore_secret: str = "change-me-in-production"
    # embedder đa ngôn ngữ (query VN): bge-m3(1024,mặc định) | e5-base | bge-base(EN) | hashing(dev)
    llm_embedder: str = "bge-m3"
    # cross-encoder reranker (hybrid RAG); rỗng = tắt rerank
    llm_reranker: str = "BAAI/bge-reranker-v2-m3"
    # số ứng viên lấy ở mỗi nhánh (dense + lexical) trước khi fuse + rerank
    rag_candidates: int = 20

    storage_dir: str = "./storage"
    # Object storage (MinIO, S3-compatible). Objects (reports, CCTV, images) are
    # served to the browser via the API /media proxy, so MinIO stays internal.
    s3_endpoint: str = "minio:9000"
    s3_access_key: str = "greenflow"
    s3_secret_key: str = "greenflow-minio-dev"
    s3_bucket: str = "greenflow"
    s3_secure: bool = False
    energyplus_bin: str = ""
    weather_epw: str = "./storage/raw/weather/hanoi.epw"
    idf_path: str = "./data/greenflow_archetype.idf"

    enable_auto_actions: bool = True
    max_setpoint_delta_c: float = 1.5
    min_occupancy_confidence: float = 0.8
    # A pending action auto-expires if not approved within this many real minutes —
    # a stale control action executed late is meaningless.
    action_approval_ttl_minutes: int = 5

    default_building_id: str = "b0000000-0000-0000-0000-000000000001"
    replay_speed_seconds: int = 10
    # Digital-twin "now": telemetry is a recorded year (2025) replayed. Pin to a
    # day (ISO, e.g. 2025-07-30T14:00:00) so the demo lands on a hot peak day;
    # empty = max(telemetry timestamp). See greenflow/replayclock.py.
    replay_now: str = ""

    # comma-separated list of allowed frontend origins for CORS
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

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

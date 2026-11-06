from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ManualIQ"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./manualiq.db"

    embedding_provider: Literal["model2vec", "hash"] = "model2vec"
    embedding_model: str = "minishlab/potion-multilingual-128M"
    embedding_dim: int = 256

    chunk_size: int = 900
    chunk_overlap: int = 150
    top_k: int = 5
    min_similarity: float = 0.30
    fts_language: Literal["english", "spanish", "simple"] = "english"
    ingestion_mode: Literal["sync", "queued"] = "sync"
    worker_poll_seconds: float = 2.0
    worker_max_attempts: int = 3
    worker_stale_seconds: int = 900

    upload_dir: str = "./data/uploads"
    corpus_dir: str = "./data/corpus"
    max_upload_bytes: int = 25 * 1024 * 1024
    cors_origins: str = "*"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

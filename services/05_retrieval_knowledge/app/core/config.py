"""Settings read from the environment (the root `.env` in docker compose)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "retrieval"
    version: str = Field(default="0.1.0", validation_alias="GIT_SHA")
    log_level: str = "INFO"
    log_json: bool = True
    error_type_base_url: str = "https://errors.football-assistant.local"

    kb_db_path: str = "/data/kb.sqlite"
    trivia_file: str = "data/football_trivia_qa.txt"
    aliases_file: str = "data/team_aliases.json"
    # Nicknames from 07 (CONTRACT §7); empty = use the bundled file only.
    football_data_url: str = "http://football-data:8000"
    aliases_cache_seconds: float = 3600
    aliases_retry_seconds: float = 60
    aliases_timeout_seconds: float = 3

    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    # Empty = no reranking; rerank_score stays null (CONTRACT §4).
    rerank_model: str = ""
    # 0 = off. MiniLM gives Thai/English pairs low cosine, so a cut-off comes from eval.
    min_vector_score: float = 0.0
    candidate_k: int = 20
    rrf_k: int = 60

    max_body_bytes: int = 64 * 1024
    max_upsert_body_bytes: int = 5 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()

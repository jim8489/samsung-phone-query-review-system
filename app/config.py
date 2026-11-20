from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env."""

    app_name: str = "Samsung Phone Query & Review System"
    app_version: str = "1.4.0"
    environment: str = "development"
    database_url: str = "sqlite:///./data/samsung_phones.db"
    api_prefix: str = "/api"

    # The app works without an LLM. Set provider=ollama to use a local open model.
    llm_provider: Literal["auto", "none", "ollama"] = "auto"
    agent_framework: Literal["custom", "langchain"] = "langchain"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_seconds: float = 75.0
    # Bound local multi-agent generation so a review request cannot loop forever.
    agent_request_timeout_seconds: float = 35.0
    agent_total_timeout_seconds: float = 90.0
    agent_recursion_limit: int = 5
    agent_max_output_tokens: int = 384

    seed_demo_data: bool = True
    scraper_user_agent: str = (
        "SamsungPhoneQueryReview/1.0 (educational research; configure a real contact in SCRAPER_USER_AGENT)"
    )
    scraper_delay_seconds: float = 2.0
    scraper_timeout_seconds: float = 25.0
    scraper_api_key: str | None = None
    scraper_max_models_per_run: int = 15

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def ensure_sqlite_directory(database_url: str) -> None:
    """Create the parent directory for a relative or absolute SQLite database."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix) or database_url == "sqlite:///:memory:":
        return
    raw_path = database_url[len(prefix) :]
    if raw_path.startswith("/"):
        path = Path(raw_path)
    else:
        path = Path.cwd() / raw_path
    path.parent.mkdir(parents=True, exist_ok=True)

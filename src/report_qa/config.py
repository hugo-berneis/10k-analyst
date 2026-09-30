"""App settings, loaded from environment variables / `.env`.

Nothing in this codebase should call `os.environ` directly -- go through
`get_settings()` so every setting has one documented place, a type, and
(where sensible) a default.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://report_qa:report_qa@localhost:5432/report_qa"

    # SEC requires a declared User-Agent with contact info for fair access:
    # https://www.sec.gov/os/webmaster-faq#developers
    sec_user_agent: str

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    jev_api_key: str = ""
    jev_base_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

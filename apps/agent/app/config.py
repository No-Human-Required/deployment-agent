"""Application settings loaded from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_LIARA_API_BASE_URL = "https://api.liara.ir"
DEFAULT_DNS_API_BASE_URL = "https://dns-service.liara.ir"
DEFAULT_WEB_ORIGIN = "http://localhost:5173"
DEFAULT_LLM_MODEL = "deepseek-v4.1-flash"


def _load_dotenv_files() -> None:
    """Load repo-root / apps/agent `.env` into os.environ (does not override existing)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    here = Path(__file__).resolve()
    # app/config.py → …/apps/agent/app/config.py
    candidates = (
        here.parents[1] / ".env",  # apps/agent/.env
        here.parents[3] / ".env",  # repo root .env
        Path.cwd() / ".env",
    )
    seen: set[Path] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        load_dotenv(resolved, override=False)


_load_dotenv_files()


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    secrets_master_key: str | None
    liara_api_base_url: str
    liara_api_token: str | None
    llm_base_url: str | None
    llm_api_key: str | None
    llm_model: str | None
    web_origin: str
    liara_http_timeout_seconds: float
    # Live Liara writes require token AND LIARA_ALLOW_LIVE_WRITES=1 (default off).
    liara_allow_live_writes: bool

    @classmethod
    def from_env(cls) -> Settings:
        _load_dotenv_files()
        return cls(
            database_url=os.environ.get(
                "DATABASE_URL",
                "postgresql://liara:liara@localhost:5433/liara_companion",
            ),
            secrets_master_key=os.environ.get("SECRETS_MASTER_KEY") or None,
            liara_api_base_url=(
                os.environ.get("LIARA_API_BASE_URL") or DEFAULT_LIARA_API_BASE_URL
            ).rstrip("/"),
            # Bootstrap only — never log or return this value.
            liara_api_token=os.environ.get("LIARA_API_TOKEN") or None,
            llm_base_url=os.environ.get("LLM_BASE_URL") or None,
            llm_api_key=os.environ.get("LLM_API_KEY") or None,
            llm_model=os.environ.get("LLM_MODEL") or DEFAULT_LLM_MODEL,
            web_origin=os.environ.get("WEB_ORIGIN") or DEFAULT_WEB_ORIGIN,
            liara_http_timeout_seconds=float(
                os.environ.get("LIARA_HTTP_TIMEOUT_SECONDS", "30")
            ),
            liara_allow_live_writes=(
                os.environ.get("LIARA_ALLOW_LIVE_WRITES", "").strip() == "1"
            ),
        )


def get_settings() -> Settings:
    return Settings.from_env()

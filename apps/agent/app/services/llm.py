"""Aval AI / OpenAI-compatible chat client from workspace Settings.

Secrets are resolved server-side. Callers must pass labels/refs into prompts —
never SecretService values. When no API key is configured, return None so the
orchestrator uses deterministic stub mode (tests never require live Aval).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.services.settings import SettingsService


@dataclass(frozen=True, slots=True)
class LlmConfig:
    """Resolved LLM connection — api_key must not be logged or put in prompts."""

    base_url: str
    model: str
    api_key: str
    api_key_label: str


class LlmNotConfigured(LookupError):
    """No Aval/OpenAI-compatible credentials available."""


class LlmService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._settings_svc = SettingsService(session, self._settings)

    def resolve_config(
        self, workspace_id: uuid.UUID | None = None
    ) -> LlmConfig | None:
        """Return config if a key is available; otherwise None (stub mode)."""
        resolved = self._settings_svc.resolve_llm_credentials(workspace_id)
        if resolved is None:
            return None
        api_key, base_url, model, label = resolved
        return LlmConfig(
            base_url=base_url,
            model=model,
            api_key=api_key,
            api_key_label=label,
        )

    def build_chat_model(
        self,
        workspace_id: uuid.UUID | None = None,
        *,
        require: bool = False,
    ) -> BaseChatModel | None:
        """Build ChatOpenAI against Aval base URL, or None for stub mode."""
        cfg = self.resolve_config(workspace_id)
        if cfg is None:
            if require:
                raise LlmNotConfigured(
                    "Aval AI not configured — set via Settings or LLM_API_KEY "
                    "(or use deterministic stub mode)"
                )
            return None
        return ChatOpenAI(
            base_url=cfg.base_url,
            api_key=cfg.api_key,
            model=cfg.model,
            temperature=0,
        )

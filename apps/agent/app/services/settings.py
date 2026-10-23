"""Workspace settings — store secret refs; return redacted views only."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import DEFAULT_LIARA_API_BASE_URL, Settings, get_settings
from app.models.settings import WorkspaceSettings
from app.models.workspace import Workspace
from app.services.secrets import SecretNotFound, SecretService

KIND_LIARA_TOKEN = "liara_api_token"
KIND_LLM_API_KEY = "llm_api_key"
DEFAULT_WORKSPACE_NAME = "default"


@dataclass(frozen=True, slots=True)
class SettingsPublicView:
    """API-safe settings — masks/labels only; never raw secrets."""

    workspace_id: uuid.UUID
    liara_api_base_url: str
    liara_team_id: str | None
    liara_token_configured: bool
    liara_token_label: str | None
    llm_base_url: str | None
    llm_model: str | None
    llm_api_key_configured: bool
    llm_api_key_label: str | None

    def model_dump(self) -> dict[str, object]:
        return {
            "workspace_id": str(self.workspace_id),
            "liara": {
                "api_base_url": self.liara_api_base_url,
                "team_id": self.liara_team_id,
                "token_configured": self.liara_token_configured,
                "token_label": self.liara_token_label,
            },
            "aval": {
                "base_url": self.llm_base_url,
                "model": self.llm_model,
                "api_key_configured": self.llm_api_key_configured,
                "api_key_label": self.llm_api_key_label,
            },
        }


class SettingsService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._secrets = SecretService(session, self._settings)

    def resolve_workspace(self, workspace_id: uuid.UUID | None = None) -> Workspace:
        if workspace_id is not None:
            ws = self._session.get(Workspace, workspace_id)
            if ws is None:
                raise LookupError(f"workspace {workspace_id} not found")
            return ws
        ws = self._session.scalar(
            select(Workspace).where(Workspace.name == DEFAULT_WORKSPACE_NAME)
        )
        if ws is None:
            ws = Workspace(name=DEFAULT_WORKSPACE_NAME)
            self._session.add(ws)
            self._session.flush()
        return ws

    def get_or_create_row(self, workspace: Workspace) -> WorkspaceSettings:
        row = self._session.scalar(
            select(WorkspaceSettings).where(
                WorkspaceSettings.workspace_id == workspace.id
            )
        )
        if row is None:
            row = WorkspaceSettings(
                workspace_id=workspace.id,
                liara_api_base_url=self._settings.liara_api_base_url
                or DEFAULT_LIARA_API_BASE_URL,
                llm_base_url=self._settings.llm_base_url,
                llm_model=self._settings.llm_model,
            )
            self._session.add(row)
            self._session.flush()
        return row

    def get_public(
        self, workspace_id: uuid.UUID | None = None
    ) -> SettingsPublicView:
        workspace = self.resolve_workspace(workspace_id)
        row = self.get_or_create_row(workspace)
        return self._to_public(row)

    def update(
        self,
        *,
        workspace_id: uuid.UUID | None = None,
        liara_api_base_url: str | None = None,
        liara_team_id: str | None = None,
        liara_api_token: str | None = None,
        llm_base_url: str | None = None,
        llm_model: str | None = None,
        llm_api_key: str | None = None,
        clear_liara_team_id: bool = False,
    ) -> SettingsPublicView:
        """Persist settings. Raw secrets accepted once and stored via SecretService."""
        workspace = self.resolve_workspace(workspace_id)
        row = self.get_or_create_row(workspace)

        if liara_api_base_url is not None:
            cleaned = liara_api_base_url.strip().rstrip("/")
            row.liara_api_base_url = cleaned or DEFAULT_LIARA_API_BASE_URL
        if clear_liara_team_id:
            row.liara_team_id = None
        elif liara_team_id is not None:
            row.liara_team_id = liara_team_id.strip() or None
        if llm_base_url is not None:
            row.llm_base_url = llm_base_url.strip() or None
        if llm_model is not None:
            row.llm_model = llm_model.strip() or None

        if liara_api_token is not None and liara_api_token.strip():
            row.liara_token_secret_id = self._secrets.put(
                workspace,
                KIND_LIARA_TOKEN,
                liara_api_token.strip(),
                label="Liara API token",
            )
        if llm_api_key is not None and llm_api_key.strip():
            row.llm_api_key_secret_id = self._secrets.put(
                workspace,
                KIND_LLM_API_KEY,
                llm_api_key.strip(),
                label="کلید API هوش مصنوعی",
            )

        self._session.flush()
        return self._to_public(row)

    def resolve_liara_credentials(
        self, workspace_id: uuid.UUID | None = None
    ) -> tuple[str, str, str | None]:
        """Return (token, base_url, team_id). Prefers Settings store; falls back to env."""
        workspace = self.resolve_workspace(workspace_id)
        row = self.get_or_create_row(workspace)
        token: str | None = None
        if row.liara_token_secret_id is not None:
            try:
                token = self._secrets.get_value(row.liara_token_secret_id)
            except SecretNotFound:
                token = None
        if not token:
            token = self._settings.liara_api_token
        if not token:
            raise LookupError(
                "Liara API token not configured — set via Settings or LIARA_API_TOKEN"
            )
        base = row.liara_api_base_url or self._settings.liara_api_base_url
        return token, base.rstrip("/"), row.liara_team_id

    def resolve_llm_credentials(
        self, workspace_id: uuid.UUID | None = None
    ) -> tuple[str, str, str, str] | None:
        """Return (api_key, base_url, model, label) or None when stub mode is required."""
        workspace = self.resolve_workspace(workspace_id)
        row = self.get_or_create_row(workspace)
        api_key: str | None = None
        label = "کلید API هوش مصنوعی"
        if row.llm_api_key_secret_id is not None:
            try:
                api_key = self._secrets.get_value(row.llm_api_key_secret_id)
                try:
                    label = self._secrets.get_public(row.llm_api_key_secret_id).label or label
                except SecretNotFound:
                    pass
            except SecretNotFound:
                api_key = None
        if not api_key:
            api_key = self._settings.llm_api_key
            if api_key:
                label = "from environment"
        if not api_key:
            return None
        base = row.llm_base_url or self._settings.llm_base_url
        model = row.llm_model or self._settings.llm_model
        if not base or not model:
            return None
        return api_key, base.rstrip("/"), model, label

    def _to_public(self, row: WorkspaceSettings) -> SettingsPublicView:
        token_label: str | None = None
        token_configured = False
        if row.liara_token_secret_id is not None:
            try:
                view = self._secrets.get_public(row.liara_token_secret_id)
                token_configured = True
                token_label = view.label
            except SecretNotFound:
                pass
        elif self._settings.liara_api_token:
            token_configured = True
            token_label = "from environment"

        key_label: str | None = None
        key_configured = False
        if row.llm_api_key_secret_id is not None:
            try:
                view = self._secrets.get_public(row.llm_api_key_secret_id)
                key_configured = True
                key_label = view.label
            except SecretNotFound:
                pass
        elif self._settings.llm_api_key:
            key_configured = True
            key_label = "from environment"

        return SettingsPublicView(
            workspace_id=row.workspace_id,
            liara_api_base_url=row.liara_api_base_url,
            liara_team_id=row.liara_team_id,
            liara_token_configured=token_configured,
            liara_token_label=token_label,
            llm_base_url=row.llm_base_url,
            llm_model=row.llm_model,
            llm_api_key_configured=key_configured,
            llm_api_key_label=key_label,
        )

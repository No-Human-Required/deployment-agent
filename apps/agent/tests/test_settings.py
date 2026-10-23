"""Settings save/load with secret masking; API never echoes secrets."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db
from app.config import Settings
from app.db.session import reset_engine
from app.main import app
from app.models.workspace import Workspace
from app.services.settings import SettingsService


@pytest.fixture
def api_client(settings: Settings, db_session: Session) -> TestClient:
    """Wire FastAPI to the same transactional session as unit tests."""

    def _override_db():
        try:
            yield db_session
            db_session.flush()
        finally:
            pass

    def _override_settings() -> Settings:
        return settings

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_app_settings] = _override_settings
    reset_engine()
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()
        reset_engine()


def test_settings_put_get_masks_secrets(
    db_session: Session, workspace: Workspace, settings: Settings
) -> None:
    secret_token = "liara-live-token-MUST-NOT-APPEAR"
    secret_key = "aval-key-MUST-NOT-APPEAR"
    svc = SettingsService(db_session, settings)
    view = svc.update(
        workspace_id=workspace.id,
        liara_api_base_url="https://api.liara.ir",
        liara_team_id="team-abc",
        liara_api_token=secret_token,
        llm_base_url="https://api.avalai.ir/v1",
        llm_model="gpt-4o-mini",
        llm_api_key=secret_key,
    )
    dumped = json.dumps(view.model_dump())
    assert secret_token not in dumped
    assert secret_key not in dumped
    assert view.liara_token_configured is True
    assert view.llm_api_key_configured is True
    assert view.liara_team_id == "team-abc"
    assert view.llm_model == "gpt-4o-mini"

    again = svc.get_public(workspace.id)
    again_dump = json.dumps(again.model_dump())
    assert secret_token not in again_dump
    assert secret_key not in again_dump
    assert again.liara_token_configured is True


def test_settings_api_redaction(api_client: TestClient, workspace: Workspace) -> None:
    secret = "never-echo-this-token-value"
    put = api_client.put(
        "/api/settings",
        json={
            "workspace_id": str(workspace.id),
            "liara_api_token": secret,
            "liara_team_id": "tid",
            "llm_api_key": "aval-secret-too",
            "llm_model": "m1",
        },
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert secret not in json.dumps(body)
    assert "aval-secret-too" not in json.dumps(body)
    assert body["liara"]["token_configured"] is True
    assert body["aval"]["api_key_configured"] is True
    assert body["liara"]["team_id"] == "tid"

    get = api_client.get("/api/settings", params={"workspace_id": str(workspace.id)})
    assert get.status_code == 200
    assert secret not in json.dumps(get.json())
    assert get.json()["liara"]["token_configured"] is True


def test_omit_secret_keeps_previous(
    db_session: Session, workspace: Workspace, settings: Settings
) -> None:
    svc = SettingsService(db_session, settings)
    svc.update(workspace_id=workspace.id, liara_api_token="first-token-value")
    view = svc.update(
        workspace_id=workspace.id,
        liara_api_base_url="https://api.liara.ir",
        llm_model="kept-model",
    )
    assert view.liara_token_configured is True
    assert view.llm_model == "kept-model"
    token, _, _ = svc.resolve_liara_credentials(workspace.id)
    assert token == "first-token-value"

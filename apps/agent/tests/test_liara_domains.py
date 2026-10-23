"""BFF GET /api/liara/domains — mocked Liara client; no live writes."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db
from app.api.liara import _public_domain_row
from app.config import Settings
from app.db.session import reset_engine
from app.main import app
from app.models.workspace import Workspace
from app.services.liara_client import LiaraHttpError, LiaraUnauthorizedError
from app.services.settings import SettingsService


@pytest.fixture
def api_client(settings: Settings, db_session: Session) -> TestClient:
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


def test_public_domain_row_normalizes_liara_shape() -> None:
    row = _public_domain_row(
        {
            "_id": "dom-1",
            "name": "example.com",
            "status": "ACTIVE",
            "certificatesStatus": "ACTIVE",
            "type": "PROJECT",
            "project": "demo-app",
            "CNameRecord": "demo-app.liara.run",
        },
        project="demo-app",
    )
    assert row == {
        "id": "dom-1",
        "name": "example.com",
        "status": "ACTIVE",
        "certificates_status": "ACTIVE",
        "project": "demo-app",
        "type": "PROJECT",
        "cname_record": "demo-app.liara.run",
    }


def test_public_domain_row_skips_nameless() -> None:
    assert _public_domain_row({"_id": "x"}, project="app") is None


def test_list_domains_requires_token(
    api_client: TestClient, workspace: Workspace
) -> None:
    res = api_client.get(
        "/api/liara/domains",
        params={"project": "demo-app", "workspace_id": str(workspace.id)},
    )
    assert res.status_code == 400
    assert "token" in res.json()["detail"].lower()


def test_list_domains_requires_project(
    api_client: TestClient, workspace: Workspace, settings: Settings, db_session: Session
) -> None:
    SettingsService(db_session, settings).update(
        workspace_id=workspace.id, liara_api_token="tok-for-domains"
    )
    res = api_client.get(
        "/api/liara/domains",
        params={"workspace_id": str(workspace.id)},
    )
    assert res.status_code == 422


def test_list_domains_ok_mocked(
    api_client: TestClient,
    workspace: Workspace,
    settings: Settings,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    SettingsService(db_session, settings).update(
        workspace_id=workspace.id, liara_api_token="tok-for-domains"
    )

    mock_client = MagicMock()
    mock_client.list_domains.return_value = [
        {
            "_id": "dom-1",
            "name": "example.com",
            "status": "ACTIVE",
            "certificatesStatus": "PENDING",
            "type": "PROJECT",
            "project": "demo-app",
            "CNameRecord": "demo-app.liara.run",
        },
        {"_id": "skip", "name": ""},
    ]

    def _fake_client(*_args: Any, **_kwargs: Any) -> MagicMock:
        return mock_client

    monkeypatch.setattr("app.api.liara.LiaraClient", _fake_client)

    res = api_client.get(
        "/api/liara/domains",
        params={"project": "demo-app", "workspace_id": str(workspace.id)},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["project"] == "demo-app"
    assert body["source"] == "liara_domains"
    assert len(body["domains"]) == 1
    assert body["domains"][0]["name"] == "example.com"
    assert body["domains"][0]["certificates_status"] == "PENDING"
    mock_client.list_domains.assert_called_once_with(project="demo-app")


def test_list_domains_empty_ok(
    api_client: TestClient,
    workspace: Workspace,
    settings: Settings,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    SettingsService(db_session, settings).update(
        workspace_id=workspace.id, liara_api_token="tok-for-domains"
    )
    mock_client = MagicMock()
    mock_client.list_domains.return_value = []
    monkeypatch.setattr(
        "app.api.liara.LiaraClient", lambda *_a, **_k: mock_client
    )
    res = api_client.get(
        "/api/liara/domains",
        params={"project": "empty-app", "workspace_id": str(workspace.id)},
    )
    assert res.status_code == 200
    assert res.json()["domains"] == []


def test_list_domains_liara_error_is_explicit(
    api_client: TestClient,
    workspace: Workspace,
    settings: Settings,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    SettingsService(db_session, settings).update(
        workspace_id=workspace.id, liara_api_token="tok-for-domains"
    )
    mock_client = MagicMock()
    mock_client.list_domains.side_effect = LiaraUnauthorizedError(
        "bad token", status_code=401
    )
    monkeypatch.setattr(
        "app.api.liara.LiaraClient", lambda *_a, **_k: mock_client
    )
    res = api_client.get(
        "/api/liara/domains",
        params={"project": "demo-app", "workspace_id": str(workspace.id)},
    )
    assert res.status_code == 502
    detail = res.json()["detail"]
    assert detail["code"] == "unauthorized"
    assert "bad token" in detail["message"]


def test_list_domains_http_shape_error(
    api_client: TestClient,
    workspace: Workspace,
    settings: Settings,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    SettingsService(db_session, settings).update(
        workspace_id=workspace.id, liara_api_token="tok-for-domains"
    )
    mock_client = MagicMock()
    mock_client.list_domains.side_effect = LiaraHttpError(
        "Unexpected GET domains response shape"
    )
    monkeypatch.setattr(
        "app.api.liara.LiaraClient", lambda *_a, **_k: mock_client
    )
    res = api_client.get(
        "/api/liara/domains",
        params={"project": "demo-app", "workspace_id": str(workspace.id)},
    )
    assert res.status_code == 502
    assert "Unexpected" in res.json()["detail"]["message"]

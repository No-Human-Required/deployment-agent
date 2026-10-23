"""BFF GET /api/liara/projects/{name}/monitoring — mocked client; no live Liara."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db
from app.api.liara import (
    _MONITORING_LOG_LIMIT,
    _public_log_lines,
    _public_metrics_block,
    _public_project_detail,
)
from app.config import Settings
from app.db.session import reset_engine
from app.main import app
from app.models.workspace import Workspace
from app.services.liara_client import (
    LiaraHttpError,
    LiaraNotFoundError,
    LiaraUnauthorizedError,
)
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


def _seed_token(db_session: Session, settings: Settings, workspace: Workspace) -> None:
    SettingsService(db_session, settings).update(
        workspace_id=workspace.id, liara_api_token="tok-for-monitoring"
    )


def test_public_project_detail_normalizes() -> None:
    row = _public_project_detail(
        {
            "name": "demo-app",
            "project_id": "demo-app",
            "type": "node",
            "status": "RUNNING",
            "isDeployed": True,
            "planID": "g2-small",
            "region": "iran",
        },
        fallback_name="demo-app",
    )
    assert row == {
        "name": "demo-app",
        "project_id": "demo-app",
        "type": "node",
        "status": "RUNNING",
        "isDeployed": True,
        "plan_id": "g2-small",
        "region": "iran",
    }


def test_public_metrics_block_empty_is_gap() -> None:
    gaps: list[dict[str, object]] = []
    block = _public_metrics_block(None, source="cpu", gaps=gaps)
    assert block == {"available": False, "series": None}
    assert gaps[0]["source"] == "cpu"
    assert gaps[0]["reason"] == "missing_or_empty"


def test_public_metrics_block_present() -> None:
    gaps: list[dict[str, object]] = []
    series = {"data": [{"t": 1, "v": 0.2}]}
    block = _public_metrics_block(series, source="memory", gaps=gaps)
    assert block == {"available": True, "series": series}
    assert gaps == []


def test_public_log_lines_sanitizes_and_caps() -> None:
    gaps: list[dict[str, object]] = []
    raw = [
        {"message": f"line-{i}", "datetime": f"t-{i}"}
        for i in range(_MONITORING_LOG_LIMIT + 5)
    ]
    raw.append({"message": "Authorization: Bearer secret-token-xyz", "datetime": "now"})
    out = _public_log_lines(raw, gaps=gaps, limit=_MONITORING_LOG_LIMIT)
    assert out["available"] is True
    assert out["truncated"] is True
    assert len(out["lines"]) <= _MONITORING_LOG_LIMIT
    joined = " ".join(str(line["message"]) for line in out["lines"])  # type: ignore[index]
    assert "secret-token-xyz" not in joined
    assert "[redacted]" in joined or "Bearer" not in joined
    assert gaps == []


def test_public_log_lines_empty_is_gap() -> None:
    gaps: list[dict[str, object]] = []
    out = _public_log_lines([], gaps=gaps)
    assert out["available"] is False
    assert out["lines"] == []
    assert gaps[0]["reason"] == "empty"


def test_monitoring_requires_token(
    api_client: TestClient, workspace: Workspace
) -> None:
    res = api_client.get(
        "/api/liara/projects/demo-app/monitoring",
        params={"workspace_id": str(workspace.id)},
    )
    assert res.status_code == 400
    assert "token" in res.json()["detail"].lower()


def test_monitoring_ok_mocked(
    api_client: TestClient,
    workspace: Workspace,
    settings: Settings,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_token(db_session, settings, workspace)
    mock_client = MagicMock()
    mock_client.get_project.return_value = {
        "name": "demo-app",
        "project_id": "demo-app",
        "type": "node",
        "status": "RUNNING",
        "isDeployed": True,
        "planID": "free",
        "region": "iran",
    }
    mock_client.get_cpu_metrics.return_value = {"data": [{"t": 1, "v": 12}]}
    mock_client.get_memory_metrics.return_value = {"data": [{"t": 1, "v": 256}]}
    mock_client.get_logs.return_value = [
        {"message": "boot ok", "datetime": "2026-10-23T10:00:00Z"},
        {"message": "listening :3000", "datetime": "2026-10-23T10:00:01Z"},
    ]
    monkeypatch.setattr(
        "app.api.liara.LiaraClient", lambda *_a, **_k: mock_client
    )

    res = api_client.get(
        "/api/liara/projects/demo-app/monitoring",
        params={"workspace_id": str(workspace.id)},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["source"] == "liara_monitoring"
    assert body["project"]["name"] == "demo-app"
    assert body["project"]["status"] == "RUNNING"
    assert body["project"]["isDeployed"] is True
    assert body["cpu"]["available"] is True
    assert body["memory"]["available"] is True
    assert body["logs"]["available"] is True
    assert len(body["logs"]["lines"]) == 2
    assert body["gaps"] == []
    mock_client.get_project.assert_called_once_with("demo-app")
    mock_client.get_cpu_metrics.assert_called_once_with("demo-app")
    mock_client.get_memory_metrics.assert_called_once_with("demo-app")
    mock_client.get_logs.assert_called_once_with("demo-app")


def test_monitoring_empty_metrics_and_logs_are_gaps(
    api_client: TestClient,
    workspace: Workspace,
    settings: Settings,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_token(db_session, settings, workspace)
    mock_client = MagicMock()
    mock_client.get_project.return_value = {
        "name": "quiet-app",
        "status": "STOPPED",
        "isDeployed": False,
        "type": "static",
    }
    mock_client.get_cpu_metrics.return_value = None
    mock_client.get_memory_metrics.return_value = []
    mock_client.get_logs.return_value = []
    monkeypatch.setattr(
        "app.api.liara.LiaraClient", lambda *_a, **_k: mock_client
    )

    res = api_client.get(
        "/api/liara/projects/quiet-app/monitoring",
        params={"workspace_id": str(workspace.id)},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["cpu"]["available"] is False
    assert body["memory"]["available"] is False
    assert body["logs"]["available"] is False
    sources = {g["source"] for g in body["gaps"]}
    assert sources == {"cpu", "memory", "logs"}


def test_monitoring_metrics_client_error_is_soft_gap(
    api_client: TestClient,
    workspace: Workspace,
    settings: Settings,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_token(db_session, settings, workspace)
    mock_client = MagicMock()
    mock_client.get_project.return_value = {
        "name": "demo-app",
        "status": "RUNNING",
        "isDeployed": True,
        "type": "node",
    }
    mock_client.get_cpu_metrics.side_effect = LiaraHttpError(
        "Unexpected GET cpu metrics response shape"
    )
    mock_client.get_memory_metrics.return_value = {"data": [{"t": 1, "v": 1}]}
    mock_client.get_logs.side_effect = LiaraHttpError("Unexpected GET logs response shape")
    monkeypatch.setattr(
        "app.api.liara.LiaraClient", lambda *_a, **_k: mock_client
    )

    res = api_client.get(
        "/api/liara/projects/demo-app/monitoring",
        params={"workspace_id": str(workspace.id)},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["memory"]["available"] is True
    assert body["cpu"]["available"] is False
    assert body["logs"]["available"] is False
    reasons = {g["source"]: g["reason"] for g in body["gaps"]}
    assert reasons["cpu"] == "http_error"
    assert reasons["logs"] == "http_error"


def test_monitoring_project_not_found(
    api_client: TestClient,
    workspace: Workspace,
    settings: Settings,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_token(db_session, settings, workspace)
    mock_client = MagicMock()
    mock_client.get_project.side_effect = LiaraNotFoundError(
        "Liara resource not found", status_code=404
    )
    monkeypatch.setattr(
        "app.api.liara.LiaraClient", lambda *_a, **_k: mock_client
    )

    res = api_client.get(
        "/api/liara/projects/missing/monitoring",
        params={"workspace_id": str(workspace.id)},
    )
    assert res.status_code == 404
    detail = res.json()["detail"]
    assert detail["code"] == "not_found"


def test_monitoring_auth_error_is_502(
    api_client: TestClient,
    workspace: Workspace,
    settings: Settings,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_token(db_session, settings, workspace)
    mock_client = MagicMock()
    mock_client.get_project.side_effect = LiaraUnauthorizedError(
        "bad token", status_code=401
    )
    monkeypatch.setattr(
        "app.api.liara.LiaraClient", lambda *_a, **_k: mock_client
    )

    res = api_client.get(
        "/api/liara/projects/demo-app/monitoring",
        params={"workspace_id": str(workspace.id)},
    )
    assert res.status_code == 502
    detail = res.json()["detail"]
    assert detail["code"] == "unauthorized"
    assert "bad token" in detail["message"]

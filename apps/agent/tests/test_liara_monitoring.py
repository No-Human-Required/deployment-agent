"""BFF GET /api/liara/projects/{name}/monitoring — mocked client; no live Liara."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db
from app.api.liara import (
    _MONITORING_LOG_LIMIT,
    _normalize_log_timestamp,
    _plan_lookup_from_me,
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
            "scale": 1,
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
        "scale": 1,
        "default_url": "https://demo-app.liara.run",
        "kind": "app",
    }


def test_normalize_log_timestamp_ns() -> None:
    # 2026-10-23T10:00:00Z in nanoseconds
    assert _normalize_log_timestamp(1_792_749_600_000_000_000) == "2026-10-23T10:00:00Z"
    assert _normalize_log_timestamp("2026-10-23T10:00:00Z") == "2026-10-23T10:00:00Z"


def test_plan_lookup_from_me_without_cli_filter() -> None:
    me = {
        "plans": {
            "projects": {
                "enterprise-custom": {
                    "available": False,
                    "region": "germany",
                    "displayPrice": 9_000_000,
                    "RAM": {"amount": 32},
                    "CPU": {"amount": 8},
                }
            }
        }
    }
    plan = _plan_lookup_from_me(me, "enterprise-custom")
    assert plan is not None
    assert plan["id"] == "enterprise-custom"
    assert plan["price_monthly"] == 9_000_000.0
    assert plan["ram_gb"] == 32.0


def test_public_metrics_block_empty_is_gap() -> None:
    gaps: list[dict[str, object]] = []
    block = _public_metrics_block(None, source="cpu", gaps=gaps)
    assert block == {"available": False, "series": None, "latest": None}
    assert gaps[0]["source"] == "cpu"
    assert gaps[0]["reason"] == "missing_or_empty"


def test_public_metrics_block_present() -> None:
    gaps: list[dict[str, object]] = []
    series = {"data": [{"t": 1, "v": 0.2}]}
    block = _public_metrics_block(series, source="memory", gaps=gaps)
    assert block["available"] is True
    assert block["series"] == series
    assert block["latest"] == 0.2
    assert gaps == []


def test_public_metrics_block_liara_result_shape() -> None:
    gaps: list[dict[str, object]] = []
    series = {
        "end": 1,
        "result": [
            {"values": [[10, "0.01"], [20, "0.05"]], "applet": "a"},
        ],
    }
    block = _public_metrics_block(series, source="cpu", gaps=gaps)
    assert block["available"] is True
    assert block["latest"] == 0.05
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


def test_public_log_lines_accepts_v2_ts_and_stream() -> None:
    gaps: list[dict[str, object]] = []
    out = _public_log_lines(
        [
            {
                "message": "listening on :3000",
                "ts": "1792749600000000000",
                "stream": "stdout",
            }
        ],
        gaps=gaps,
    )
    assert out["available"] is True
    lines = out["lines"]
    assert isinstance(lines, list) and len(lines) == 1
    line = lines[0]
    assert isinstance(line, dict)
    assert line["message"] == "listening on :3000"
    assert line["stream"] == "stdout"
    assert line["timestamp"] == "2026-10-23T10:00:00Z"
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
    mock_client.get_cpu_metrics.return_value = {
        "result": [{"values": [[1, "0.12"]], "applet": "x"}]
    }
    mock_client.get_memory_metrics.return_value = {
        "result": [{"values": [[1, "256"]], "applet": "x"}]
    }
    mock_client.get_metrics_summary.return_value = {
        "cpuUsage": [{"value": [1, "0.15"], "applet": "x"}],
        "memoryUsage": [{"value": [1, "300"], "applet": "x"}],
    }
    mock_client.get_runtime_logs.return_value = [
        {
            "message": "boot ok",
            "ts": "1792749600000000000",
            "stream": "stdout",
        },
        {
            "message": "listening :3000",
            "ts": "1792749601000000000",
            "stream": "stdout",
        },
    ]
    mock_client.list_domains.return_value = [
        {
            "_id": "dom-1",
            "name": "app.example.com",
            "status": "ACTIVE",
            "certificatesStatus": "ACTIVE",
            "project": "demo-app",
            "type": "SUBDOMAIN",
        }
    ]
    mock_client.get_me.return_value = {
        "plans": {
            "projects": {
                "free": {
                    "available": True,
                    "region": "iran",
                    "displayPrice": 0,
                    "RAM": {"amount": 0.5},
                    "CPU": {"amount": 0.5},
                }
            }
        }
    }
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
    assert body["project"]["default_url"] == "https://demo-app.liara.run"
    assert body["plan"]["id"] == "free"
    assert body["plan"]["price_monthly"] == 0.0
    assert len(body["domains"]) == 1
    assert body["domains"][0]["name"] == "app.example.com"
    assert body["cpu"]["available"] is True
    assert body["cpu"]["latest"] == 0.15
    assert body["memory"]["available"] is True
    assert body["memory"]["latest"] == 300.0
    assert body["logs"]["available"] is True
    assert len(body["logs"]["lines"]) == 2
    assert body["logs"]["lines"][0]["timestamp"] == "2026-10-23T10:00:00Z"
    assert body["logs"]["lines"][0]["stream"] == "stdout"
    assert body["gaps"] == []
    mock_client.get_project.assert_called_once_with("demo-app")
    mock_client.get_cpu_metrics.assert_called_once_with("demo-app")
    mock_client.get_memory_metrics.assert_called_once_with("demo-app")
    mock_client.get_runtime_logs.assert_called_once_with("demo-app")
    mock_client.list_domains.assert_called_once_with(project="demo-app")
    mock_client.get_me.assert_called_once()
    mock_client.get_metrics_summary.assert_called_once_with("demo-app")


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
    mock_client.get_metrics_summary.return_value = None
    mock_client.get_runtime_logs.return_value = []
    mock_client.list_domains.return_value = []
    mock_client.get_me.return_value = {"plans": {"projects": {}}}
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
    assert body["domains"] == []
    assert body["plan"] is None
    sources = {g["source"] for g in body["gaps"]}
    assert {"cpu", "memory", "logs"}.issubset(sources)


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
        "planID": "free",
    }
    mock_client.get_metrics_summary.return_value = None
    mock_client.get_cpu_metrics.side_effect = LiaraHttpError(
        "Unexpected GET cpu metrics response shape"
    )
    mock_client.get_memory_metrics.return_value = {"data": [{"t": 1, "v": 1}]}
    mock_client.get_runtime_logs.side_effect = LiaraHttpError(
        "Unexpected GET v2 logs response shape"
    )
    mock_client.list_domains.side_effect = LiaraHttpError("domains unavailable")
    mock_client.get_me.side_effect = LiaraHttpError("me unavailable")
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
    assert body["domains"] == []
    assert body["plan"] is None
    reasons = {g["source"]: g["reason"] for g in body["gaps"]}
    assert reasons["cpu"] == "http_error"
    assert reasons["logs"] == "http_error"
    assert reasons["domains"] == "http_error"
    assert reasons["plan"] == "http_error"


def test_list_services_includes_apps_and_databases(
    api_client: TestClient,
    workspace: Workspace,
    settings: Settings,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_token(db_session, settings, workspace)
    mock_client = MagicMock()
    mock_client.list_projects.return_value = [
        {
            "project_id": "demo-app",
            "type": "node",
            "status": "ACTIVE",
            "isDeployed": True,
            "planID": "small-g2",
        }
    ]
    mock_client.list_databases.return_value = [
        {
            "id": "db-1",
            "hostname": "demo-postgres",
            "type": "postgres",
            "status": "RUNNING",
            "planID": "small-g2",
        }
    ]
    monkeypatch.setattr(
        "app.api.liara.LiaraClient", lambda *_a, **_k: mock_client
    )
    res = api_client.get(
        "/api/liara/services",
        params={"workspace_id": str(workspace.id)},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["source"] == "liara_services"
    kinds = {row["kind"] for row in body["services"]}
    assert kinds == {"app", "database"}
    names = {row["name"] for row in body["services"]}
    assert names == {"demo-app", "demo-postgres"}


def test_database_monitoring_ok(
    api_client: TestClient,
    workspace: Workspace,
    settings: Settings,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_token(db_session, settings, workspace)
    mock_client = MagicMock()
    mock_client.get_database.return_value = {
        "database": {
            "id": "db-1",
            "hostname": "demo-postgres",
            "type": "postgres",
            "status": "RUNNING",
            "planID": "small-g2",
            "version": "16.14",
            "volumeSize": 5,
            "publicNetwork": False,
            "root_password": "secret-should-not-leak",
        }
    }
    mock_client.get_me.return_value = {
        "plans": {
            "databases": {
                "small-g2": {
                    "available": True,
                    "region": "iran",
                    "displayPrice": 475_000,
                    "RAM": {"amount": 1},
                }
            }
        }
    }
    monkeypatch.setattr(
        "app.api.liara.LiaraClient", lambda *_a, **_k: mock_client
    )
    res = api_client.get(
        "/api/liara/databases/db-1/monitoring",
        params={"workspace_id": str(workspace.id)},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["source"] == "liara_database_monitoring"
    assert body["project"]["name"] == "demo-postgres"
    assert body["project"]["kind"] == "database"
    assert body["project"]["version"] == "16.14"
    assert body["plan"]["id"] == "small-g2"
    assert body["plan"]["price_monthly"] == 475_000.0
    assert body["domains"] == []
    assert "secret" not in str(body).lower()
    assert body["cpu"]["available"] is False
    assert body["logs"]["available"] is False
    assert any(g["reason"] == "not_applicable" for g in body["gaps"])
    assert any(g["source"] == "domains" for g in body["gaps"])


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

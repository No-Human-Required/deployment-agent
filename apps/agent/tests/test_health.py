"""Health / ready endpoints."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_always_ok() -> None:
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_ready_reports_database() -> None:
    client = TestClient(app)
    res = client.get("/ready")
    assert res.status_code == 200
    body = res.json()
    assert "database" in body
    assert body["status"] in {"ready", "degraded"}

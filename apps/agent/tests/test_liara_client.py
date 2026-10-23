"""LiaraClient error classification + prove-read with httpx mock transport."""

from __future__ import annotations

import json

import httpx
import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.services.liara_client import (
    LiaraClient,
    LiaraForbiddenError,
    LiaraNotFoundError,
    LiaraRateLimitError,
    LiaraTimeoutError,
    LiaraUnauthorizedError,
    sanitize_for_log,
)
from app.services.prove_liara import prove_and_mark_tested
from app.services.registry import CapabilityRegistry
from app.services.settings import SettingsService
from app.models.workspace import Workspace


def _mock_transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_sanitize_redacts_bearer_tokens() -> None:
    raw = 'Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig leaked'
    cleaned = sanitize_for_log(raw)
    assert "eyJ" not in cleaned
    assert "[redacted]" in cleaned


def test_get_me_and_projects_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer test-token"
        if request.url.path == "/v1/me":
            return httpx.Response(200, json={"user": {"email": "a@b.c", "name": "A"}})
        if request.url.path == "/v1/projects":
            assert request.url.params.get("teamID") == "team-1"
            return httpx.Response(
                200,
                json={
                    "projects": [
                        {
                            "project_id": "app-1",
                            "type": "nodejs",
                            "status": "RUNNING",
                            "isDeployed": True,
                        }
                    ]
                },
            )
        return httpx.Response(404, json={"message": "nope"})

    client = LiaraClient(
        "test-token",
        team_id="team-1",
        transport=_mock_transport(handler),
    )
    result = client.prove_read_access()
    assert result.project_count == 1
    assert result.projects[0]["project_id"] == "app-1"
    assert result.me["email"] == "a@b.c"


@pytest.mark.parametrize(
    ("status", "exc_type"),
    [
        (401, LiaraUnauthorizedError),
        (403, LiaraForbiddenError),
        (404, LiaraNotFoundError),
        (429, LiaraRateLimitError),
    ],
)
def test_status_classification(status: int, exc_type: type[Exception]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            text=f'{{"error":"fail","token":"Bearer secret-should-not-leak"}}',
        )

    client = LiaraClient("tok", transport=_mock_transport(handler))
    with pytest.raises(exc_type) as caught:
        client.get_me()
    assert caught.value.status_code == status
    assert caught.value.code in {
        "unauthorized",
        "forbidden",
        "not_found",
        "rate_limited",
    }


def test_timeout_classification() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = LiaraClient("tok", transport=_mock_transport(handler), timeout=0.1)
    with pytest.raises(LiaraTimeoutError) as caught:
        client.list_projects()
    assert caught.value.code == "timeout"


def test_prove_marks_list_get_projects_tested(
    db_session: Session, workspace: Workspace, settings: Settings
) -> None:
    registry = CapabilityRegistry(db_session)
    registry.seed()
    assert registry.get("list_get_projects").status == "documented"

    settings_svc = SettingsService(db_session, settings)
    settings_svc.update(
        workspace_id=workspace.id,
        liara_api_token="mock-token-value",
        liara_team_id="t1",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/me":
            return httpx.Response(200, json={"user": {"email": "x@y.z"}})
        if request.url.path == "/v1/projects":
            return httpx.Response(200, json={"projects": []})
        return httpx.Response(500)

    client = LiaraClient("mock-token-value", transport=_mock_transport(handler))
    outcome = prove_and_mark_tested(
        db_session,
        workspace_id=workspace.id,
        settings=settings,
        client=client,
    )
    assert outcome.ok
    assert outcome.registry_updated is True
    assert outcome.registry_status == "tested"
    assert registry.get("list_get_projects").status == "tested"

    # Second prove leaves tested (no re-transition to tested).
    outcome2 = prove_and_mark_tested(
        db_session,
        workspace_id=workspace.id,
        settings=settings,
        client=client,
    )
    assert outcome2.registry_updated is False
    assert outcome2.registry_status == "tested"


def test_error_body_not_logged_with_raw_bearer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "Bearer super-secret-token-xyz"
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=json.dumps({"hint": secret}))

    client = LiaraClient("tok", transport=_mock_transport(handler))
    with caplog.at_level("WARNING"):
        with pytest.raises(LiaraUnauthorizedError):
            client.get_me()
    assert "super-secret-token-xyz" not in caplog.text

"""Secret roundtrip, redaction, and fail-closed put."""

from __future__ import annotations

import json
import logging
import uuid

import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.secret import SecretRef
from app.models.workspace import Workspace
from app.services.secrets import (
    SecretPublicView,
    SecretService,
    SecretsMasterKeyMissing,
)


def test_secret_roundtrip(
    db_session: Session, workspace: Workspace, settings: Settings
) -> None:
    svc = SecretService(db_session, settings)
    plaintext = "liara-token-super-secret-value"
    ref_id = svc.put(workspace, "liara_api_token", plaintext, label="Liara API")
    assert isinstance(ref_id, uuid.UUID)

    row = db_session.get(SecretRef, ref_id)
    assert row is not None
    assert row.ciphertext != plaintext.encode()
    assert plaintext.encode() not in row.ciphertext

    assert svc.get_value(ref_id) == plaintext


def test_secret_repr_and_public_dump_redact_plaintext(
    db_session: Session, workspace: Workspace, settings: Settings
) -> None:
    plaintext = "aval-ai-key-MUST-NOT-LEAK"
    svc = SecretService(db_session, settings)
    ref_id = svc.put(workspace, "aval_api_key", plaintext, label="Aval")
    row = db_session.get(SecretRef, ref_id)
    assert row is not None

    rendered = repr(row)
    assert plaintext not in rendered
    assert "ciphertext=***" in rendered

    public = row.to_public_dict()
    dumped = json.dumps(public)
    assert plaintext not in dumped
    assert "ciphertext" not in public
    assert "value" not in public

    view = svc.get_public(ref_id)
    assert isinstance(view, SecretPublicView)
    view_dump = json.dumps(view.model_dump())
    assert plaintext not in view_dump
    assert "ciphertext" not in view_dump


def test_logging_secret_public_view_does_not_include_value(
    db_session: Session,
    workspace: Workspace,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plaintext = "never-log-me-please"
    svc = SecretService(db_session, settings)
    ref_id = svc.put(workspace, "liara_api_token", plaintext)
    view = svc.get_public(ref_id)

    with caplog.at_level(logging.INFO):
        logging.getLogger("test_secrets").info("stored secret %s", view.model_dump())

    assert plaintext not in caplog.text


def test_put_fails_closed_without_master_key(
    db_session: Session, workspace: Workspace, database_url: str
) -> None:
    bare = Settings(
        database_url=database_url,
        secrets_master_key=None,
        liara_api_base_url="https://api.liara.ir",
        liara_api_token=None,
        llm_base_url=None,
        llm_api_key=None,
        llm_model=None,
        web_origin="http://localhost:3000",
        liara_http_timeout_seconds=5.0,
        liara_allow_live_writes=False,
    )
    svc = SecretService(db_session, bare)
    with pytest.raises(SecretsMasterKeyMissing):
        svc.put(workspace, "liara_api_token", "x")

"""Shared fixtures — isolated test Postgres only (never the live companion DB).

Pytest must not share ``liara_companion`` with the running agent. Historical
``drop_all`` on ``DATABASE_URL`` wiped Settings secrets and conversations.
"""

from __future__ import annotations

import os
import uuid
from urllib.parse import urlparse, urlunparse

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.base import Base
from app.models import (  # noqa: F401
    Approval,
    AuditEvent,
    Capability,
    Case,
    ConversationThread,
    Incident,
    Monitor,
    Operation,
    Plan,
    RecoveryBaseline,
    SecretRef,
    Workspace,
    WorkspaceFolder,
    WorkspaceMember,
    WorkspaceSettings,
)

# Ensure models are registered on metadata before create_all
import app.models  # noqa: F401, E402

# Live / seeded companion DBs — refuse any destructive schema ops on these.
_PROTECTED_DB_NAMES = frozenset(
    {
        "liara_companion",
        "postgres",
        "template0",
        "template1",
    }
)

_DEFAULT_TEST_DATABASE_URL = (
    "postgresql://liara:liara@localhost:5433/liara_companion_test"
)


def pytest_sessionstart(session: pytest.Session) -> None:
    """Fail fast if env points pytest at the live companion database."""
    _ = session
    # Unit tests must not auto-enable live DevOps create tools from a developer .env.
    os.environ.pop("LIARA_ALLOW_LIVE_WRITES", None)
    for key in ("TEST_DATABASE_URL", "PYTEST_DATABASE_URL"):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            _assert_safe_test_database(raw)
            return
    # Default target must also be safe (guards against editing the default badly).
    _assert_safe_test_database(_DEFAULT_TEST_DATABASE_URL)


def _database_name(url: str) -> str:
    path = urlparse(url).path.lstrip("/")
    return path.split("?")[0] if path else ""


def _assert_safe_test_database(url: str) -> str:
    name = _database_name(url)
    if not name:
        raise RuntimeError(f"test DATABASE URL has no database name: {url!r}")
    if name in _PROTECTED_DB_NAMES:
        raise RuntimeError(
            f"Refusing to run pytest against protected database {name!r}. "
            f"Use TEST_DATABASE_URL (default: liara_companion_test), "
            f"not DATABASE_URL / liara_companion."
        )
    if not name.endswith("_test") and os.environ.get("ALLOW_NON_TEST_DB") != "1":
        raise RuntimeError(
            f"Refusing database {name!r}: test DB name must end with '_test' "
            f"(or set ALLOW_NON_TEST_DB=1 for an intentional exception)."
        )
    return name


def _admin_url(url: str) -> str:
    """Same host/user, database ``postgres`` — for CREATE DATABASE."""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path="/postgres"))


def _ensure_database_exists(url: str) -> None:
    name = _assert_safe_test_database(url)
    admin = create_engine(_admin_url(url), isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": name},
            ).scalar()
            if not exists:
                # Identifier only — name already validated against allowlist rules.
                conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def database_url() -> str:
    """Always the isolated test DB — never fall back to live ``DATABASE_URL``."""
    raw = (
        os.environ.get("TEST_DATABASE_URL")
        or os.environ.get("PYTEST_DATABASE_URL")
        or _DEFAULT_TEST_DATABASE_URL
    ).strip()
    # If someone exports DATABASE_URL into the shell and mistakenly sets
    # TEST_DATABASE_URL to the same value, the guard below still blocks.
    if not os.environ.get("TEST_DATABASE_URL") and not os.environ.get(
        "PYTEST_DATABASE_URL"
    ):
        live = (os.environ.get("DATABASE_URL") or "").strip()
        if live and _database_name(live) == _database_name(raw):
            raise RuntimeError(
                "DATABASE_URL points at the same DB pytest would use; "
                "set TEST_DATABASE_URL to a dedicated *_test database."
            )
    _assert_safe_test_database(raw)
    return raw


@pytest.fixture(scope="session")
def master_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture(scope="session")
def engine(database_url: str) -> Engine:
    _assert_safe_test_database(database_url)
    _ensure_database_exists(database_url)
    eng = create_engine(database_url, pool_pre_ping=True)
    with eng.connect() as conn:
        conn.execute(text("SELECT 1"))
    # Destructive reset is allowed only on the isolated *_test database.
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def settings(database_url: str, master_key: str) -> Settings:
    return Settings(
        database_url=database_url,
        secrets_master_key=master_key,
        liara_api_base_url="https://api.liara.ir",
        liara_api_token=None,
        llm_base_url=None,
        llm_api_key=None,
        llm_model=None,
        web_origin="http://localhost:3000",
        liara_http_timeout_seconds=5.0,
        liara_allow_live_writes=False,
    )


@pytest.fixture
def db_session(engine: Engine) -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def workspace(db_session: Session) -> Workspace:
    ws = Workspace(name=f"ws-{uuid.uuid4().hex[:8]}")
    db_session.add(ws)
    db_session.flush()
    return ws

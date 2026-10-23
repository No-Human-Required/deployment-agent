"""Shared fixtures — Postgres via DATABASE_URL, isolated transactions."""

from __future__ import annotations

import os
import uuid

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.base import Base
from app.models import (  # noqa: F401
    Approval,
    AuditEvent,
    Capability,
    Case,
    Incident,
    Monitor,
    Operation,
    Plan,
    RecoveryBaseline,
    SecretRef,
    Workspace,
    WorkspaceMember,
    WorkspaceSettings,
)

# Ensure models are registered on metadata before create_all
import app.models  # noqa: F401, E402


@pytest.fixture(scope="session")
def database_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://liara:liara@localhost:5433/liara_companion",
    )


@pytest.fixture(scope="session")
def master_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture(scope="session")
def engine(database_url: str):
    eng = create_engine(database_url, pool_pre_ping=True)
    # Connectivity check early — fail tests clearly if Postgres is down.
    with eng.connect() as conn:
        conn.execute(text("SELECT 1"))
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()
    # Restore Alembic schema so local migrate/seed still work after pytest.
    # (drop_all leaves alembic_version pointing at head with no tables.)
    _restore_alembic_schema(database_url)


def _restore_alembic_schema(database_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.stamp(cfg, "base")
    command.upgrade(cfg, "head")


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
def db_session(engine) -> Session:
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

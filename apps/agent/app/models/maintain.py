"""Phase-6 maintain entities: Monitor, Incident, RecoveryBaseline, WorkspaceMember."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ROLE_OWNER = "owner"
ROLE_VIEWER = "viewer"
ALLOWED_ROLES = frozenset({ROLE_OWNER, ROLE_VIEWER})


class WorkspaceMember(Base):
    """Minimal product roles — owner may write; viewer is read-only."""

    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "actor_id",
            name="uq_workspace_members_workspace_actor",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=ROLE_OWNER)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Monitor(Base):
    """Health monitor — enable ≠ approve restart / write."""

    __tablename__ = "monitors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target: Mapped[str] = mapped_column(String(255), nullable=False)  # project name
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    criteria: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    notification_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    # Status of last check: ok | alert | stale | error | never
    last_status: Mapped[str] = mapped_column(
        String(64), nullable=False, default="never"
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_data_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consecutive_misses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Enabling monitor never grants write / restart permission.
    grants_write_permission: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Incident(Base):
    """Deduped alert grouping — open / resolve with evidence."""

    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "dedupe_key",
            name="uq_incidents_workspace_dedupe",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    monitor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("monitors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="alert")
    alert_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Alert never implies restart/write authorization.
    write_authorized: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolve_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)


class RecoveryBaseline(Base):
    """Sanitized snapshot taken before sensitive writes — recovery needs fresh approval."""

    __tablename__ = "recovery_baselines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Sanitized only — secret refs, never secret values.
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_operation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("operations.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

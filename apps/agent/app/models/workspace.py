"""Workspace / Target — Phase 0 tenancy root."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.audit import AuditEvent
    from app.models.case import Case
    from app.models.conversation import ConversationThread, WorkspaceFolder
    from app.models.secret import SecretRef
    from app.models.settings import WorkspaceSettings


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    cases: Mapped[list[Case]] = relationship("Case", back_populates="workspace")
    secret_refs: Mapped[list[SecretRef]] = relationship(
        "SecretRef", back_populates="workspace"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        "AuditEvent", back_populates="workspace"
    )
    settings: Mapped[WorkspaceSettings | None] = relationship(
        "WorkspaceSettings",
        back_populates="workspace",
        uselist=False,
    )
    folders: Mapped[list[WorkspaceFolder]] = relationship(
        "WorkspaceFolder", back_populates="workspace"
    )
    conversation_threads: Mapped[list[ConversationThread]] = relationship(
        "ConversationThread", back_populates="workspace"
    )

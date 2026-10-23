"""Chat threads + local project folders — persisted in Postgres (not browser storage)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class WorkspaceFolder(Base):
    """Local project folder known to a companion workspace (machine path)."""

    __tablename__ = "workspace_folders"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "path",
            name="uq_workspace_folders_workspace_path",
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
    path: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="folders")


class ConversationThread(Base):
    """UI chat thread scoped to a local folder within a companion workspace."""

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "id",
            name="uq_conversations_workspace_id",
        ),
    )

    # Client-generated short ids (Vite shell); not Postgres UUID.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    folder_key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    service_id: Mapped[str] = mapped_column(String(255), nullable=False, default="workspace")
    context_services: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    messages: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    orchestrator_run: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    workspace: Mapped[Workspace] = relationship(
        "Workspace", back_populates="conversation_threads"
    )

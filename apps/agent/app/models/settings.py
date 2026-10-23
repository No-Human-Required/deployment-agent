"""Per-workspace product settings — secret refs only for tokens/keys."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.secret import SecretRef
    from app.models.workspace import Workspace


class WorkspaceSettings(Base):
    __tablename__ = "workspace_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Plaintext-ok identifiers / URLs (not secrets)
    liara_api_base_url: Mapped[str] = mapped_column(
        String(512), nullable=False, default="https://api.liara.ir"
    )
    liara_team_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    llm_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(255), nullable=True)

    liara_token_secret_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("secret_refs.id", ondelete="SET NULL"),
        nullable=True,
    )
    llm_api_key_secret_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("secret_refs.id", ondelete="SET NULL"),
        nullable=True,
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

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="settings")
    liara_token_secret: Mapped[SecretRef | None] = relationship(
        "SecretRef", foreign_keys=[liara_token_secret_id]
    )
    llm_api_key_secret: Mapped[SecretRef | None] = relationship(
        "SecretRef", foreign_keys=[llm_api_key_secret_id]
    )

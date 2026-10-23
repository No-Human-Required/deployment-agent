"""SecretRef — ciphertext only; never store or repr plaintext."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class SecretRef(Base):
    __tablename__ = "secret_refs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    workspace: Mapped[Workspace] = relationship(
        "Workspace", back_populates="secret_refs"
    )

    def __repr__(self) -> str:
        return (
            f"SecretRef(id={self.id!r}, workspace_id={self.workspace_id!r}, "
            f"kind={self.kind!r}, label={self.label!r}, ciphertext=***)"
        )

    def to_public_dict(self) -> dict[str, object]:
        """Safe dump for API / logging — never includes ciphertext or plaintext."""
        return {
            "id": str(self.id),
            "workspace_id": str(self.workspace_id),
            "kind": self.kind,
            "label": self.label,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

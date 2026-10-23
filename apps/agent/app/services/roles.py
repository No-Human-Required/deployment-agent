"""Minimal workspace roles — owner may write; viewer is read-only.

Product roles do not elevate Liara account permissions.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.maintain import (
    ALLOWED_ROLES,
    ROLE_OWNER,
    ROLE_VIEWER,
    WorkspaceMember,
)


class RoleDeniedError(PermissionError):
    def __init__(self, message: str = "role cannot perform this action") -> None:
        super().__init__(message)
        self.code = "role_denied"


class RolesService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_member(
        self,
        *,
        workspace_id: uuid.UUID,
        actor_id: str,
        role: str,
    ) -> WorkspaceMember:
        role = role.strip().lower()
        if role not in ALLOWED_ROLES:
            raise ValueError(f"invalid role: {role}")
        actor_id = actor_id.strip()
        if not actor_id:
            raise ValueError("actor_id required")

        existing = self._session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.actor_id == actor_id,
            )
        )
        if existing is not None:
            existing.role = role
            self._session.flush()
            return existing

        member = WorkspaceMember(
            workspace_id=workspace_id,
            actor_id=actor_id,
            role=role,
        )
        self._session.add(member)
        self._session.flush()
        return member

    def get_role(
        self, *, workspace_id: uuid.UUID, actor_id: str | None
    ) -> str | None:
        if not actor_id or not actor_id.strip():
            return None
        member = self._session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.actor_id == actor_id.strip(),
            )
        )
        return member.role if member else None

    def require_write(
        self, *, workspace_id: uuid.UUID, actor_id: str | None
    ) -> str:
        """Owner may write. Viewer / unknown / missing actor → denied."""
        role = self.get_role(workspace_id=workspace_id, actor_id=actor_id)
        if role == ROLE_OWNER:
            return ROLE_OWNER
        if role == ROLE_VIEWER:
            raise RoleDeniedError("viewer cannot execute writes")
        # Fail closed when actor is absent or unregistered on write routes.
        raise RoleDeniedError("write requires workspace owner role")

    def can_write(self, *, workspace_id: uuid.UUID, actor_id: str | None) -> bool:
        try:
            self.require_write(workspace_id=workspace_id, actor_id=actor_id)
            return True
        except RoleDeniedError:
            return False

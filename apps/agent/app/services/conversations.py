"""Persist chat threads and local folders in Postgres."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.conversation import ConversationThread, WorkspaceFolder
from app.services.settings import SettingsService

MAX_PER_FOLDER = 8
MAX_RECENT_FOLDERS = 8
UNSCOPED_KEY = "__unscoped__"


def normalize_folder_key(path: str) -> str:
    value = path.strip().replace("\x00", "")
    if not value:
        return ""
    if len(value) > 1:
        value = value.rstrip("/\\")
    return value


def folder_display_name(path: str) -> str:
    key = normalize_folder_key(path)
    parts = [p for p in key.replace("\\", "/").split("/") if p]
    return parts[-1] if parts else key


class ConversationStore:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._settings = SettingsService(session)

    def _workspace(self, workspace_id: uuid.UUID | None):
        return self._settings.resolve_workspace(workspace_id)

    # --- folders ---------------------------------------------------------------

    def list_folders(
        self, workspace_id: uuid.UUID | None = None
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id)
        rows = list(
            self._session.scalars(
                select(WorkspaceFolder)
                .where(WorkspaceFolder.workspace_id == workspace.id)
                .order_by(WorkspaceFolder.updated_at.desc())
            )
        )
        recent = [
            {
                "version": 1,
                "path": row.path,
                "displayName": row.display_name,
            }
            for row in rows[:MAX_RECENT_FOLDERS]
        ]
        active = next((r for r in rows if r.is_active), None)
        workspace_payload = (
            {
                "version": 1,
                "path": active.path,
                "displayName": active.display_name,
            }
            if active
            else None
        )
        return {
            "workspace_id": str(workspace.id),
            "workspace": workspace_payload,
            "recent": recent,
        }

    def save_folder(
        self,
        *,
        workspace_id: uuid.UUID | None,
        path: str | None,
        display_name: str | None = None,
        clear_active: bool = False,
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id)

        if clear_active or path is None:
            for row in self._session.scalars(
                select(WorkspaceFolder).where(
                    WorkspaceFolder.workspace_id == workspace.id,
                    WorkspaceFolder.is_active.is_(True),
                )
            ):
                row.is_active = False
            self._session.flush()
            return self.list_folders(workspace.id)

        key = normalize_folder_key(path)
        if not key or key == UNSCOPED_KEY:
            raise ValueError("invalid folder path")

        name = (display_name or "").strip() or folder_display_name(key)
        now = datetime.now(timezone.utc)

        for row in self._session.scalars(
            select(WorkspaceFolder).where(WorkspaceFolder.workspace_id == workspace.id)
        ):
            row.is_active = False

        existing = self._session.scalar(
            select(WorkspaceFolder).where(
                WorkspaceFolder.workspace_id == workspace.id,
                WorkspaceFolder.path == key,
            )
        )
        if existing is None:
            existing = WorkspaceFolder(
                workspace_id=workspace.id,
                path=key,
                display_name=name,
                is_active=True,
                updated_at=now,
            )
            self._session.add(existing)
        else:
            existing.display_name = name
            existing.is_active = True
            existing.updated_at = now

        self._session.flush()

        # Cap recent folders (keep most recently updated).
        rows = list(
            self._session.scalars(
                select(WorkspaceFolder)
                .where(WorkspaceFolder.workspace_id == workspace.id)
                .order_by(WorkspaceFolder.updated_at.desc())
            )
        )
        for stale in rows[MAX_RECENT_FOLDERS:]:
            self._session.delete(stale)
        self._session.flush()
        return self.list_folders(workspace.id)

    def activate_folder(
        self, *, workspace_id: uuid.UUID | None, path: str
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id)
        key = normalize_folder_key(path)
        found = self._session.scalar(
            select(WorkspaceFolder).where(
                WorkspaceFolder.workspace_id == workspace.id,
                WorkspaceFolder.path == key,
            )
        )
        if found is None:
            raise LookupError("folder not found")
        return self.save_folder(
            workspace_id=workspace.id,
            path=found.path,
            display_name=found.display_name,
        )

    # --- conversations ---------------------------------------------------------

    def _row_to_dict(self, row: ConversationThread) -> dict[str, Any]:
        updated = row.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return {
            "id": row.id,
            "title": row.title,
            "serviceId": row.service_id,
            "contextServices": row.context_services or [],
            "messages": row.messages or [],
            "updatedAt": updated.isoformat().replace("+00:00", "Z"),
            "orchestratorRun": row.orchestrator_run,
            "folderKey": row.folder_key,
        }

    def list_for_folder(
        self, *, workspace_id: uuid.UUID | None, folder_key: str | None
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id)
        if not folder_key:
            return {"workspace_id": str(workspace.id), "conversations": []}
        key = normalize_folder_key(folder_key)
        if not key or key == UNSCOPED_KEY:
            return {"workspace_id": str(workspace.id), "conversations": []}
        rows = list(
            self._session.scalars(
                select(ConversationThread)
                .where(
                    ConversationThread.workspace_id == workspace.id,
                    ConversationThread.folder_key == key,
                )
                .order_by(ConversationThread.updated_at.desc())
                .limit(MAX_PER_FOLDER)
            )
        )
        return {
            "workspace_id": str(workspace.id),
            "conversations": [self._row_to_dict(r) for r in rows],
        }

    def list_all(self, *, workspace_id: uuid.UUID | None) -> dict[str, Any]:
        workspace = self._workspace(workspace_id)
        rows = list(
            self._session.scalars(
                select(ConversationThread).where(
                    ConversationThread.workspace_id == workspace.id
                )
            )
        )
        by_folder: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            key = normalize_folder_key(row.folder_key)
            if not key or key == UNSCOPED_KEY:
                continue
            by_folder.setdefault(key, []).append(self._row_to_dict(row))
        for key, items in by_folder.items():
            items.sort(key=lambda c: c["updatedAt"], reverse=True)
            by_folder[key] = items[:MAX_PER_FOLDER]
        return {"workspace_id": str(workspace.id), "byWorkspace": by_folder}

    def find_by_id(
        self, *, workspace_id: uuid.UUID | None, conversation_id: str
    ) -> dict[str, Any] | None:
        workspace = self._workspace(workspace_id)
        row = self._session.get(ConversationThread, conversation_id)
        if row is None or row.workspace_id != workspace.id:
            return None
        return {
            "workspaceKey": row.folder_key,
            "conversation": self._row_to_dict(row),
        }

    def replace_folder(
        self,
        *,
        workspace_id: uuid.UUID | None,
        folder_key: str,
        conversations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id)
        key = normalize_folder_key(folder_key)
        if not key or key == UNSCOPED_KEY:
            raise ValueError("invalid folder key")

        self._session.execute(
            delete(ConversationThread).where(
                ConversationThread.workspace_id == workspace.id,
                ConversationThread.folder_key == key,
            )
        )

        kept: list[ConversationThread] = []
        for raw in conversations[:MAX_PER_FOLDER]:
            cid = str(raw.get("id") or "").strip()
            title = str(raw.get("title") or "").strip()
            if not cid or not title:
                continue
            messages = raw.get("messages")
            if not isinstance(messages, list):
                messages = []
            context = raw.get("contextServices")
            if not isinstance(context, list):
                context = []
            service_id = str(raw.get("serviceId") or "workspace")
            orch = raw.get("orchestratorRun")
            if orch is not None and not isinstance(orch, dict):
                orch = None
            updated_raw = raw.get("updatedAt")
            try:
                updated_at = (
                    datetime.fromisoformat(str(updated_raw).replace("Z", "+00:00"))
                    if updated_raw
                    else datetime.now(timezone.utc)
                )
            except ValueError:
                updated_at = datetime.now(timezone.utc)

            row = ConversationThread(
                id=cid[:64],
                workspace_id=workspace.id,
                folder_key=key,
                title=title[:512],
                service_id=service_id[:255],
                context_services=context[:8],
                messages=messages,
                orchestrator_run=orch,
                updated_at=updated_at,
            )
            self._session.add(row)
            kept.append(row)

        self._session.flush()
        return {
            "workspace_id": str(workspace.id),
            "conversations": [self._row_to_dict(r) for r in kept],
        }

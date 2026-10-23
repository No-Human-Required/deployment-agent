"""Chat history + local folders — Postgres-backed (replaces browser localStorage)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.conversations import ConversationStore

router = APIRouter(prefix="/api", tags=["conversations"])


class FolderSaveBody(BaseModel):
    workspace_id: uuid.UUID | None = None
    path: str | None = None
    displayName: str | None = None
    clear_active: bool = False


class FolderActivateBody(BaseModel):
    workspace_id: uuid.UUID | None = None
    path: str = Field(min_length=1)


class ConversationReplaceBody(BaseModel):
    workspace_id: uuid.UUID | None = None
    folder_key: str = Field(min_length=1)
    conversations: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/folders")
def get_folders(
    db: Annotated[Session, Depends(get_db)],
    workspace_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    return ConversationStore(db).list_folders(workspace_id)


@router.put("/folders")
def put_folder(
    body: FolderSaveBody,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    try:
        return ConversationStore(db).save_folder(
            workspace_id=body.workspace_id,
            path=body.path,
            display_name=body.displayName,
            clear_active=body.clear_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/folders/activate")
def activate_folder(
    body: FolderActivateBody,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    try:
        return ConversationStore(db).activate_folder(
            workspace_id=body.workspace_id, path=body.path
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/conversations")
def get_conversations(
    db: Annotated[Session, Depends(get_db)],
    workspace_id: Annotated[uuid.UUID | None, Query()] = None,
    folder_key: Annotated[str | None, Query()] = None,
    all_folders: Annotated[bool, Query()] = False,
) -> dict[str, object]:
    store = ConversationStore(db)
    if all_folders:
        return store.list_all(workspace_id=workspace_id)
    return store.list_for_folder(workspace_id=workspace_id, folder_key=folder_key)


@router.get("/conversations/by-id/{conversation_id}")
def get_conversation_by_id(
    conversation_id: str,
    db: Annotated[Session, Depends(get_db)],
    workspace_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    found = ConversationStore(db).find_by_id(
        workspace_id=workspace_id, conversation_id=conversation_id
    )
    if found is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return found


@router.put("/conversations")
def put_conversations(
    body: ConversationReplaceBody,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    try:
        return ConversationStore(db).replace_folder(
            workspace_id=body.workspace_id,
            folder_key=body.folder_key,
            conversations=body.conversations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

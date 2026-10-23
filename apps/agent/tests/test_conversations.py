"""Postgres-backed conversation + folder persistence."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db
from app.config import Settings
from app.db.session import reset_engine
from app.main import app
from app.models.workspace import Workspace
from app.services.conversations import ConversationStore


def test_folder_and_conversation_round_trip(
    db_session: Session, workspace: Workspace, settings: Settings
) -> None:
    def _override_db():
        try:
            yield db_session
            db_session.flush()
        finally:
            pass

    def _override_settings() -> Settings:
        return settings

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_app_settings] = _override_settings
    reset_engine()
    client = TestClient(app)
    try:
        folder = "/Users/me/demo-app"
        put_folder = client.put(
            "/api/folders",
            json={
                "workspace_id": str(workspace.id),
                "path": f"{folder}/",
                "displayName": "demo-app",
            },
        )
        assert put_folder.status_code == 200
        body = put_folder.json()
        assert body["workspace"]["path"] == folder
        assert body["recent"][0]["path"] == folder

        conversation = {
            "id": "c1",
            "title": "دیپلوی اولیه",
            "serviceId": "workspace",
            "contextServices": [],
            "messages": [{"id": "m1", "role": "user", "text": "دیپلوی کن"}],
            "updatedAt": "2026-10-23T12:00:00.000Z",
            "orchestratorRun": None,
        }
        put_chats = client.put(
            "/api/conversations",
            json={
                "workspace_id": str(workspace.id),
                "folder_key": folder,
                "conversations": [conversation],
            },
        )
        assert put_chats.status_code == 200
        assert put_chats.json()["conversations"][0]["id"] == "c1"

        listed = client.get(
            "/api/conversations",
            params={"workspace_id": str(workspace.id), "folder_key": folder},
        )
        assert listed.status_code == 200
        assert listed.json()["conversations"][0]["title"] == "دیپلوی اولیه"

        found = client.get(
            "/api/conversations/by-id/c1",
            params={"workspace_id": str(workspace.id)},
        )
        assert found.status_code == 200
        assert found.json()["workspaceKey"] == folder
    finally:
        app.dependency_overrides.clear()
        reset_engine()


def test_store_isolates_folders(db_session: Session, workspace: Workspace) -> None:
    store = ConversationStore(db_session)
    store.replace_folder(
        workspace_id=workspace.id,
        folder_key="/a",
        conversations=[
            {
                "id": "a1",
                "title": "A",
                "serviceId": "workspace",
                "messages": [],
                "updatedAt": "2026-10-23T12:00:00.000Z",
            }
        ],
    )
    store.replace_folder(
        workspace_id=workspace.id,
        folder_key="/b",
        conversations=[
            {
                "id": "b1",
                "title": "B",
                "serviceId": "workspace",
                "messages": [],
                "updatedAt": "2026-10-23T12:00:00.000Z",
            }
        ],
    )
    assert [
        c["id"]
        for c in store.list_for_folder(workspace_id=workspace.id, folder_key="/a")[
            "conversations"
        ]
    ] == ["a1"]
    assert [
        c["id"]
        for c in store.list_for_folder(workspace_id=workspace.id, folder_key="/b")[
            "conversations"
        ]
    ] == ["b1"]

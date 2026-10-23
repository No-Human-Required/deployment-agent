"""Prove Liara read access and promote list_get_projects → tested."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.services.liara_client import LiaraClient, ProveReadResult
from app.services.registry import CapabilityRegistry
from app.services.settings import SettingsService

LIST_GET_PROJECTS = "list_get_projects"


@dataclass(frozen=True, slots=True)
class ProveReadOutcome:
    ok: bool
    prove: ProveReadResult
    registry_status: str
    registry_updated: bool

    def model_dump(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "me": self.prove.me,
            "project_count": self.prove.project_count,
            "projects": self.prove.projects,
            "registry": {
                "tool_id": LIST_GET_PROJECTS,
                "status": self.registry_status,
                "updated": self.registry_updated,
            },
        }


def prove_and_mark_tested(
    session: Session,
    *,
    workspace_id: uuid.UUID | None = None,
    settings: Settings | None = None,
    client: LiaraClient | None = None,
) -> ProveReadOutcome:
    """
    Call GET /v1/me + GET /v1/projects; on success set list_get_projects to tested
    (documented → tested only; already-tested left unchanged; never enables writes).
    """
    cfg = settings or get_settings()
    settings_svc = SettingsService(session, cfg)
    if client is None:
        token, base_url, team_id = settings_svc.resolve_liara_credentials(workspace_id)
        client = LiaraClient(
            token,
            base_url=base_url,
            team_id=team_id,
            timeout=cfg.liara_http_timeout_seconds,
        )
    prove = client.prove_read_access()

    registry = CapabilityRegistry(session)
    # Fresh DBs often have an empty catalog — seed before promoting status.
    registry.seed()
    cap = registry.get(LIST_GET_PROJECTS)
    updated = False
    if cap.status == "documented":
        cap = registry.set_status(LIST_GET_PROJECTS, "tested")
        updated = True
    return ProveReadOutcome(
        ok=True,
        prove=prove,
        registry_status=cap.status,
        registry_updated=updated,
    )

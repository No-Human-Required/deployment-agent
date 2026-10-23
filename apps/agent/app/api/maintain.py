"""Phase-6 BFF: monitors, incidents, recovery draft, audit list, roles.

Monitor enable ≠ write permission. Recovery execute reuses approve+execute_plan.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db
from app.config import Settings
from app.services.maintain import incident_to_card, monitor_to_status
from app.services.orchestrator import (
    OrchestratorError,
    OrchestratorService,
    RoleForbiddenError,
)
from app.services.roles import RolesService
from app.services.write_guard import WriteGuard

router = APIRouter(prefix="/api/maintain", tags=["maintain"])


def _service(
    db: Session,
    settings: Settings,
) -> OrchestratorService:
    return OrchestratorService(db, settings, write_guard=WriteGuard())


def _http_error(exc: OrchestratorError) -> HTTPException:
    status = 400
    if exc.code in (
        "monitor_not_found",
        "incident_not_found",
        "baseline_not_found",
        "case_not_found",
    ):
        status = 404
    elif exc.code == "role_denied":
        status = 403
    elif exc.code in ("monitor_invalid", "incident_invalid", "recovery_invalid"):
        status = 422
    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": str(exc)},
    )


class EnableMonitorBody(BaseModel):
    workspace_id: uuid.UUID
    target: str = Field(min_length=1, max_length=255)
    case_id: uuid.UUID | None = None
    interval_seconds: int = Field(default=60, ge=10, le=86400)
    criteria: dict[str, Any] | None = None
    notification_allowed: bool = True
    monitor_id: uuid.UUID | None = None
    actor_id: str | None = None


class DisableMonitorBody(BaseModel):
    workspace_id: uuid.UUID
    monitor_id: uuid.UUID
    actor_id: str | None = None


class RunCheckBody(BaseModel):
    workspace_id: uuid.UUID
    monitor_id: uuid.UUID


class ResolveIncidentBody(BaseModel):
    workspace_id: uuid.UUID
    incident_id: uuid.UUID
    evidence: str = Field(min_length=1, max_length=4000)
    actor_id: str | None = None


class RecoveryPlanBody(BaseModel):
    workspace_id: uuid.UUID
    case_id: uuid.UUID
    project_name: str = Field(min_length=1, max_length=255)
    action: Literal["restart", "republish"] = "restart"
    baseline_id: uuid.UUID | None = None
    actor_id: str | None = None


class UpsertMemberBody(BaseModel):
    workspace_id: uuid.UUID
    actor_id: str = Field(min_length=1, max_length=255)
    role: Literal["owner", "viewer"]


@router.post("/monitors/enable")
def enable_monitor(
    body: EnableMonitorBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        status = svc.enable_monitor(
            workspace_id=body.workspace_id,
            target=body.target,
            case_id=body.case_id,
            interval_seconds=body.interval_seconds,
            criteria=body.criteria,
            notification_allowed=body.notification_allowed,
            monitor_id=body.monitor_id,
            actor_id=body.actor_id,
        )
    except RoleForbiddenError as exc:
        raise _http_error(exc) from exc
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    payload = status.model_dump(mode="json")
    payload["grants_write_permission"] = False
    return payload


@router.post("/monitors/disable")
def disable_monitor(
    body: DisableMonitorBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        status = svc.disable_monitor(
            workspace_id=body.workspace_id,
            monitor_id=body.monitor_id,
            actor_id=body.actor_id,
        )
    except RoleForbiddenError as exc:
        raise _http_error(exc) from exc
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return status.model_dump(mode="json")


@router.get("/monitors/{monitor_id}")
def get_monitor(
    monitor_id: uuid.UUID,
    workspace_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        mon = svc.maintain().get_monitor(
            workspace_id=workspace_id, monitor_id=monitor_id
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "monitor_not_found", "message": str(exc)},
        ) from exc
    return monitor_to_status(mon).model_dump(mode="json")


@router.post("/monitors/check")
def run_monitor_check(
    body: RunCheckBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    """Periodic check stub — alert does not authorize writes."""
    svc = _service(db, app_settings)
    try:
        return svc.run_monitor_check(
            workspace_id=body.workspace_id, monitor_id=body.monitor_id
        )
    except OrchestratorError as exc:
        raise _http_error(exc) from exc


@router.post("/incidents/resolve")
def resolve_incident(
    body: ResolveIncidentBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        card = svc.resolve_incident(
            workspace_id=body.workspace_id,
            incident_id=body.incident_id,
            evidence=body.evidence,
            actor_id=body.actor_id,
        )
    except RoleForbiddenError as exc:
        raise _http_error(exc) from exc
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return card.model_dump(mode="json")


@router.get("/incidents")
def list_incidents(
    workspace_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
    status: str | None = None,
) -> dict[str, object]:
    svc = _service(db, app_settings)
    rows = svc.maintain().list_incidents(workspace_id=workspace_id, status=status)
    return {
        "incidents": [
            incident_to_card(i).model_dump(mode="json") for i in rows
        ]
    }


@router.post("/recovery/plan")
def create_recovery_plan(
    body: RecoveryPlanBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    """Draft recovery — requires separate approve_plan + execute_plan."""
    svc = _service(db, app_settings)
    try:
        plan, validated, view = svc.create_recovery_plan(
            workspace_id=body.workspace_id,
            case_id=body.case_id,
            project_name=body.project_name,
            action=body.action,
            baseline_id=body.baseline_id,
            actor_id=body.actor_id,
        )
    except RoleForbiddenError as exc:
        raise _http_error(exc) from exc
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return {
        "plan_id": str(plan.id),
        "version": plan.version,
        "content_hash": plan.content_hash,
        "body": validated.model_dump(mode="json"),
        "recovery": view.model_dump(mode="json"),
        "requires_fresh_approval": True,
    }


@router.get("/audit")
def list_audit(
    workspace_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
    case_id: uuid.UUID | None = None,
    limit: int = 50,
) -> dict[str, object]:
    """Sanitized audit events — no secret values."""
    svc = _service(db, app_settings)
    events = svc.list_audit_events(
        workspace_id=workspace_id, case_id=case_id, limit=limit
    )
    return {"events": events}


@router.post("/members")
def upsert_member(
    body: UpsertMemberBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    _ = app_settings
    member = RolesService(db).upsert_member(
        workspace_id=body.workspace_id,
        actor_id=body.actor_id,
        role=body.role,
    )
    return {
        "id": str(member.id),
        "workspace_id": str(member.workspace_id),
        "actor_id": member.actor_id,
        "role": member.role,
    }

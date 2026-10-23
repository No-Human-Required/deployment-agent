"""BFF command routes for orchestrator stubs.

Commands: assess_readiness, create_plan, approve_plan, execute_plan,
continue_or_stop, verify_result, collect_evidence, diagnose,
propose_fix_options, verify_fix, create_patch, run_patch_sandbox,
approve_patch_record, approve_release. Model JSON never executes provider writes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db
from app.config import Settings
from app.services.orchestrator import (
    ApprovalExpiredError,
    ApprovalRequiredError,
    OrchestratorError,
    OrchestratorService,
    PlanHashMismatchError,
    RoleForbiddenError,
    SchemaValidationError,
)
from app.services.write_guard import WriteGuard

router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])


def _service(
    db: Session,
    settings: Settings,
    write_guard: WriteGuard | None = None,
) -> OrchestratorService:
    return OrchestratorService(db, settings, write_guard=write_guard or WriteGuard())


def _http_error(exc: OrchestratorError) -> HTTPException:
    status = 400
    if exc.code in (
        "case_not_found",
        "plan_not_found",
        "operation_not_found",
        "evidence_not_found",
        "diagnosis_not_found",
        "fix_options_not_found",
        "fix_option_not_found",
        "patch_not_found",
        "patch_base_path_missing",
    ):
        status = 404
    elif exc.code in (
        "approval_required",
        "approval_expired",
        "plan_hash_mismatch",
        "release_blocked_sandbox",
        "release_blocked_red_tests",
        "patch_record_required",
        "patch_record_mismatch",
        "sandbox_required",
    ):
        status = 409
    elif exc.code == "role_denied":
        status = 403
    elif exc.code == "schema_invalid":
        status = 422
    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": str(exc)},
    )


class AssessBody(BaseModel):
    workspace_id: uuid.UUID
    case_id: uuid.UUID
    app_path: str | None = None


class CreatePlanBody(BaseModel):
    workspace_id: uuid.UUID
    case_id: uuid.UUID
    plan: dict[str, Any] | None = None
    goal: str | None = None
    use_llm: bool = False
    deploy: dict[str, Any] | None = None
    ops: dict[str, Any] | None = None
    deps: dict[str, Any] | None = None


class DiscoverDependenciesBody(BaseModel):
    workspace_id: uuid.UUID
    case_id: uuid.UUID
    app_path: str = Field(min_length=1)
    project_name: str | None = None


class ResumeOperationBody(BaseModel):
    workspace_id: uuid.UUID
    operation_id: uuid.UUID | None = None
    client_request_id: str | None = None


class ApprovePlanBody(BaseModel):
    workspace_id: uuid.UUID
    plan_id: uuid.UUID
    scope: dict[str, Any] | None = None
    expires_at: datetime | None = None


class ExecutePlanBody(BaseModel):
    workspace_id: uuid.UUID
    plan_id: uuid.UUID
    client_request_id: str = Field(min_length=1, max_length=128)
    # When set, owner/viewer roles are enforced (viewer → 403).
    actor_id: str | None = None


class ContinueOrStopBody(BaseModel):
    workspace_id: uuid.UUID
    operation_id: uuid.UUID
    decision: str = Field(pattern="^(continue|stop)$")


class VerifyBody(BaseModel):
    workspace_id: uuid.UUID
    operation_id: uuid.UUID


class CreateCaseBody(BaseModel):
    workspace_id: uuid.UUID
    goal: str = Field(min_length=1)


class CollectEvidenceBody(BaseModel):
    workspace_id: uuid.UUID
    case_id: uuid.UUID
    project_name: str = Field(min_length=1, max_length=128)
    symptom: str | None = None
    window_note: str | None = None


class DiagnoseBody(BaseModel):
    workspace_id: uuid.UUID
    case_id: uuid.UUID
    evidence_version: str = Field(min_length=8, max_length=128)
    diagnosis: dict[str, Any] | None = None


class ProposeFixOptionsBody(BaseModel):
    workspace_id: uuid.UUID
    case_id: uuid.UUID
    diagnosis_version: str = Field(min_length=8, max_length=128)
    project_name: str = Field(min_length=1, max_length=128)
    plan_id_for_resize: str | None = None


class CreatePlanFromFixBody(BaseModel):
    workspace_id: uuid.UUID
    case_id: uuid.UUID
    option_id: str = Field(min_length=1, max_length=64)


class VerifyFixBody(BaseModel):
    workspace_id: uuid.UUID
    case_id: uuid.UUID
    operation_id: uuid.UUID
    method: str = "get_project_health"
    project_name: str | None = None


class CreatePatchBody(BaseModel):
    workspace_id: uuid.UUID
    case_id: uuid.UUID
    evidence_version: str = Field(min_length=8, max_length=128)
    diagnosis_version: str = Field(min_length=8, max_length=128)
    app_path: str = Field(min_length=1)
    hypothesis_id: str | None = Field(default=None, max_length=64)
    unified_diff: str | None = None
    rationale: str | None = None


class RunPatchSandboxBody(BaseModel):
    workspace_id: uuid.UUID
    case_id: uuid.UUID
    patch_version: str = Field(min_length=8, max_length=128)
    # Tests may set True when rehearsing under an external network policy.
    network_policy_available: bool | None = None
    command_key: str = "pytest_fixture"


class ApprovePatchRecordBody(BaseModel):
    workspace_id: uuid.UUID
    case_id: uuid.UUID
    patch_version: str = Field(min_length=8, max_length=128)
    expires_at: datetime | None = None


class ApproveReleaseBody(BaseModel):
    workspace_id: uuid.UUID
    case_id: uuid.UUID
    patch_version: str = Field(min_length=8, max_length=128)
    project_name: str = Field(min_length=1, max_length=128)
    archive_path: str = Field(min_length=1)
    port: int = 3000
    platform: str = "node"
    expires_at: datetime | None = None


@router.post("/cases")
def create_case(
    body: CreateCaseBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        case = svc.ensure_case(workspace_id=body.workspace_id, goal=body.goal)
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return {"id": str(case.id), "workspace_id": str(case.workspace_id), "goal": case.goal}


@router.post("/assess_readiness")
def assess_readiness(
    body: AssessBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        result = svc.assess_readiness(
            workspace_id=body.workspace_id,
            case_id=body.case_id,
            app_path=body.app_path,
        )
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return result.model_dump(mode="json")


@router.post("/create_plan")
def create_plan(
    body: CreatePlanBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        if body.goal:
            svc.ensure_case(
                workspace_id=body.workspace_id,
                case_id=body.case_id,
                goal=body.goal,
            )
        plan, validated = svc.create_plan(
            workspace_id=body.workspace_id,
            case_id=body.case_id,
            plan_draft=body.plan,
            use_llm=body.use_llm,
            deploy=body.deploy,
            ops=body.ops,
            deps=body.deps,
        )
    except SchemaValidationError as exc:
        raise _http_error(exc) from exc
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return {
        "plan_id": str(plan.id),
        "version": plan.version,
        "content_hash": plan.content_hash,
        "body": validated.model_dump(mode="json"),
    }


@router.post("/approve_plan")
def approve_plan(
    body: ApprovePlanBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        approval = svc.approve_plan(
            workspace_id=body.workspace_id,
            plan_id=body.plan_id,
            scope=body.scope,
            expires_at=body.expires_at,
        )
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return {
        "approval_id": str(approval.id),
        "plan_id": str(approval.plan_id),
        "plan_hash": approval.plan_hash,
        "status": approval.status,
        "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
        "scope": approval.scope,
    }


@router.post("/execute_plan")
def execute_plan(
    body: ExecutePlanBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        op = svc.execute_plan(
            workspace_id=body.workspace_id,
            plan_id=body.plan_id,
            client_request_id=body.client_request_id,
            actor_id=body.actor_id,
        )
    except (
        SchemaValidationError,
        ApprovalRequiredError,
        ApprovalExpiredError,
        PlanHashMismatchError,
        RoleForbiddenError,
        OrchestratorError,
    ) as exc:
        raise _http_error(exc) from exc
    return svc.operation_payload(op).model_dump(mode="json")


@router.post("/continue_or_stop")
def continue_or_stop(
    body: ContinueOrStopBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        op = svc.continue_or_stop(
            workspace_id=body.workspace_id,
            operation_id=body.operation_id,
            decision=body.decision,
        )
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return svc.operation_payload(op).model_dump(mode="json")


@router.post("/verify_result")
def verify_result(
    body: VerifyBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        op = svc.verify_result(
            workspace_id=body.workspace_id,
            operation_id=body.operation_id,
        )
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return svc.operation_payload(op).model_dump(mode="json")


@router.post("/discover_dependencies")
def discover_dependencies(
    body: DiscoverDependenciesBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    """Phase-4: file-backed DB/Redis/disk discovery + GenUI dependency_plan."""
    svc = _service(db, app_settings)
    try:
        payload = svc.discover_dependencies(
            workspace_id=body.workspace_id,
            case_id=body.case_id,
            app_path=body.app_path,
            project_name=body.project_name,
        )
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return payload.model_dump(mode="json")


@router.post("/collect_evidence")
def collect_evidence(
    body: CollectEvidenceBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        pack = svc.collect_evidence(
            workspace_id=body.workspace_id,
            case_id=body.case_id,
            project_name=body.project_name,
            symptom=body.symptom,
            window_note=body.window_note,
        )
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return pack.model_dump(mode="json")


@router.post("/diagnose")
def diagnose(
    body: DiagnoseBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        diagnosis = svc.diagnose(
            workspace_id=body.workspace_id,
            case_id=body.case_id,
            evidence_version=body.evidence_version,
            diagnosis_draft=body.diagnosis,
        )
    except SchemaValidationError as exc:
        raise _http_error(exc) from exc
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return diagnosis.model_dump(mode="json")


@router.post("/propose_fix_options")
def propose_fix_options(
    body: ProposeFixOptionsBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        payload = svc.propose_fix_options(
            workspace_id=body.workspace_id,
            case_id=body.case_id,
            diagnosis_version=body.diagnosis_version,
            project_name=body.project_name,
            plan_id_for_resize=body.plan_id_for_resize,
        )
    except SchemaValidationError as exc:
        raise _http_error(exc) from exc
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return payload.model_dump(mode="json")


@router.post("/create_plan_from_fix")
def create_plan_from_fix(
    body: CreatePlanFromFixBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        plan, validated = svc.create_plan_from_fix_option(
            workspace_id=body.workspace_id,
            case_id=body.case_id,
            option_id=body.option_id,
        )
    except SchemaValidationError as exc:
        raise _http_error(exc) from exc
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return {
        "plan_id": str(plan.id),
        "version": plan.version,
        "content_hash": plan.content_hash,
        "body": validated.model_dump(mode="json"),
    }


@router.post("/verify_fix")
def verify_fix(
    body: VerifyFixBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = _service(db, app_settings)
    try:
        result = svc.verify_fix(
            workspace_id=body.workspace_id,
            case_id=body.case_id,
            operation_id=body.operation_id,
            method=body.method,
            project_name=body.project_name,
        )
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return result.model_dump(mode="json")


@router.post("/create_patch")
def create_patch(
    body: CreatePatchBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    """Phase-5: limited unified diff tied to evidence/diagnosis (no release)."""
    svc = _service(db, app_settings)
    try:
        payload = svc.create_patch(
            workspace_id=body.workspace_id,
            case_id=body.case_id,
            evidence_version=body.evidence_version,
            diagnosis_version=body.diagnosis_version,
            app_path=body.app_path,
            hypothesis_id=body.hypothesis_id,
            unified_diff=body.unified_diff,
            rationale=body.rationale,
        )
    except SchemaValidationError as exc:
        raise _http_error(exc) from exc
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return payload.model_dump(mode="json")


@router.post("/run_patch_sandbox")
def run_patch_sandbox(
    body: RunPatchSandboxBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    """Phase-5: apply on temp copy, scrub secrets, allowlisted tests."""
    svc = _service(db, app_settings)
    try:
        payload = svc.run_patch_sandbox(
            workspace_id=body.workspace_id,
            case_id=body.case_id,
            patch_version=body.patch_version,
            network_policy_available=body.network_policy_available,
            command_key=body.command_key,
        )
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return payload.model_dump(mode="json")


@router.post("/approve_patch_record")
def approve_patch_record(
    body: ApprovePatchRecordBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    """HITL: record patch only — distinct from approve_release."""
    svc = _service(db, app_settings)
    try:
        plan, approval, payload = svc.approve_patch_record(
            workspace_id=body.workspace_id,
            case_id=body.case_id,
            patch_version=body.patch_version,
            expires_at=body.expires_at,
        )
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return {
        "plan_id": str(plan.id),
        "approval_id": str(approval.id),
        "plan_hash": approval.plan_hash,
        "status": approval.status,
        "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
        "scope": approval.scope,
        "patch_diff": payload.model_dump(mode="json"),
    }


@router.post("/approve_release")
def approve_release(
    body: ApproveReleaseBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    """HITL: Liara release — blocked when sandbox not ready_for_release."""
    svc = _service(db, app_settings)
    try:
        plan, approval, payload = svc.approve_release(
            workspace_id=body.workspace_id,
            case_id=body.case_id,
            patch_version=body.patch_version,
            project_name=body.project_name,
            archive_path=body.archive_path,
            port=body.port,
            platform=body.platform,
            expires_at=body.expires_at,
        )
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return {
        "plan_id": str(plan.id),
        "approval_id": str(approval.id),
        "plan_hash": approval.plan_hash,
        "status": approval.status,
        "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
        "scope": approval.scope,
        "patch_diff": payload.model_dump(mode="json"),
    }


@router.get("/operations/{operation_id}")
def get_operation(
    operation_id: uuid.UUID,
    workspace_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    """Load durable Operation by id — session/worker resume (no write)."""
    svc = _service(db, app_settings)
    try:
        op = svc.get_operation(
            workspace_id=workspace_id, operation_id=operation_id
        )
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return svc.operation_payload(op).model_dump(mode="json")


@router.post("/resume_operation")
def resume_operation(
    body: ResumeOperationBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    """Resume after session restart simulation — load only, no duplicate write."""
    svc = _service(db, app_settings)
    try:
        op = svc.resume_operation(
            workspace_id=body.workspace_id,
            operation_id=body.operation_id,
            client_request_id=body.client_request_id,
        )
    except OrchestratorError as exc:
        raise _http_error(exc) from exc
    return svc.operation_payload(op).model_dump(mode="json")

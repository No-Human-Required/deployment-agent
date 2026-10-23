"""Orchestrator core — schema fail-closed, approval gate, idempotency, expiry."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.types import Command
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.case import Case
from app.models.stubs import Plan
from app.models.workspace import Workspace
from app.orchestrator.graph import build_orchestrator_graph
from app.schemas.orchestration import PlanVersion
from app.services.orchestrator import (
    ApprovalExpiredError,
    ApprovalRequiredError,
    OrchestratorService,
    SchemaValidationError,
    plan_content_hash,
)
from app.services.write_guard import WriteGuard


VALID_PLAN = {
    "version": 1,
    "steps": [
        {
            "id": "s1",
            "action": "create_project_stub",
            "tool_id": "create_project",
            "effects": ["would_create"],
            "cost_known": False,
            "params": {},
        }
    ],
    "effects": ["would_create"],
    "cost_known": False,
    "cost_summary": "unknown",
    "summary": "test plan",
}


@pytest.fixture
def case(db_session: Session, workspace: Workspace) -> Case:
    c = Case(
        workspace_id=workspace.id,
        goal="Deploy demo app",
        status="open",
    )
    db_session.add(c)
    db_session.flush()
    return c


@pytest.fixture
def guard() -> WriteGuard:
    return WriteGuard()


@pytest.fixture
def orch(
    db_session: Session, settings: Settings, guard: WriteGuard
) -> OrchestratorService:
    return OrchestratorService(db_session, settings, write_guard=guard)


def test_schema_invalid_plan_zero_writes(
    orch: OrchestratorService,
    workspace: Workspace,
    case: Case,
    guard: WriteGuard,
) -> None:
    with pytest.raises(SchemaValidationError):
        orch.create_plan(
            workspace_id=workspace.id,
            case_id=case.id,
            plan_draft={"version": 1, "steps": []},  # invalid: empty steps
        )
    assert guard.call_count == 0
    assert db_plan_count(orch, case.id) == 0


def test_schema_invalid_llm_json_zero_writes(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
) -> None:
    guard = WriteGuard()
    fake = FakeListChatModel(responses=["not-json-at-all {{{"])
    orch = OrchestratorService(
        db_session, settings, write_guard=guard, chat_model=fake
    )
    with pytest.raises(SchemaValidationError):
        orch.create_plan(
            workspace_id=workspace.id,
            case_id=case.id,
            use_llm=True,
        )
    assert guard.call_count == 0


def test_execute_without_approval_fails_closed(
    orch: OrchestratorService,
    workspace: Workspace,
    case: Case,
    guard: WriteGuard,
) -> None:
    plan, _ = orch.create_plan(
        workspace_id=workspace.id,
        case_id=case.id,
        plan_draft=VALID_PLAN,
    )
    with pytest.raises(ApprovalRequiredError):
        orch.execute_plan(
            workspace_id=workspace.id,
            plan_id=plan.id,
            client_request_id="req-1",
        )
    assert guard.call_count == 0


def test_approval_expiry_rejects_execute(
    orch: OrchestratorService,
    workspace: Workspace,
    case: Case,
    guard: WriteGuard,
) -> None:
    plan, _ = orch.create_plan(
        workspace_id=workspace.id,
        case_id=case.id,
        plan_draft=VALID_PLAN,
    )
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    orch.approve_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        expires_at=past,
    )
    with pytest.raises(ApprovalExpiredError):
        orch.execute_plan(
            workspace_id=workspace.id,
            plan_id=plan.id,
            client_request_id="req-expired",
            now=datetime.now(timezone.utc),
        )
    assert guard.call_count == 0


def test_duplicate_execute_request_id_returns_same_operation(
    orch: OrchestratorService,
    workspace: Workspace,
    case: Case,
    guard: WriteGuard,
) -> None:
    plan, _ = orch.create_plan(
        workspace_id=workspace.id,
        case_id=case.id,
        plan_draft=VALID_PLAN,
    )
    orch.approve_plan(workspace_id=workspace.id, plan_id=plan.id)
    op1 = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="idem-42",
    )
    calls_after_first = guard.call_count
    op2 = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="idem-42",
    )
    assert op1.id == op2.id
    assert guard.call_count == calls_after_first  # no re-write


def test_approve_then_execute_records_stub_operation(
    orch: OrchestratorService,
    workspace: Workspace,
    case: Case,
    guard: WriteGuard,
) -> None:
    plan, validated = orch.create_plan(
        workspace_id=workspace.id,
        case_id=case.id,
        plan_draft=VALID_PLAN,
    )
    assert plan.content_hash == plan_content_hash(validated)
    approval = orch.approve_plan(workspace_id=workspace.id, plan_id=plan.id)
    assert approval.plan_hash == plan.content_hash
    op = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="req-ok",
    )
    assert guard.call_count >= 1
    assert op.state == "awaiting_provider"
    assert op.client_request_id == "req-ok"
    verified = orch.verify_result(workspace_id=workspace.id, operation_id=op.id)
    assert verified.state == "verified_stub"


def test_graph_interrupt_gates_execute(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
) -> None:
    guard = WriteGuard()
    orch = OrchestratorService(db_session, settings, write_guard=guard)
    graph = build_orchestrator_graph(orch)
    thread = {"configurable": {"thread_id": f"t-{uuid.uuid4().hex}"}}

    # Run until HITL interrupt at await_approval
    result = graph.invoke(
        {
            "workspace_id": str(workspace.id),
            "case_id": str(case.id),
            "goal": case.goal,
            "plan_body": VALID_PLAN,
            "client_request_id": f"graph-{uuid.uuid4().hex[:8]}",
        },
        config=thread,
    )
    # Before resume, no provider write
    assert guard.call_count == 0
    assert "__interrupt__" in result or result.get("plan_id")

    # Reject path
    rejected = graph.invoke(
        Command(resume={"approved": False}),
        config=thread,
    )
    assert guard.call_count == 0
    assert rejected.get("error") == "approval_rejected" or rejected.get("approved") is False


def test_graph_resume_approve_then_execute(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
) -> None:
    guard = WriteGuard()
    orch = OrchestratorService(db_session, settings, write_guard=guard)
    graph = build_orchestrator_graph(orch)
    thread = {"configurable": {"thread_id": f"t-{uuid.uuid4().hex}"}}
    client_request_id = f"graph-ok-{uuid.uuid4().hex[:8]}"

    graph.invoke(
        {
            "workspace_id": str(workspace.id),
            "case_id": str(case.id),
            "goal": case.goal,
            "plan_body": VALID_PLAN,
            "client_request_id": client_request_id,
        },
        config=thread,
    )
    assert guard.call_count == 0

    final = graph.invoke(
        Command(resume={"approved": True}),
        config=thread,
    )
    assert guard.call_count >= 1
    assert final.get("operation_id")
    assert final.get("verification", {}).get("state") == "verified_stub"


def test_plan_version_schema_rejects_empty_steps() -> None:
    with pytest.raises(Exception):
        PlanVersion.model_validate({"version": 1, "steps": []})


def db_plan_count(orch: OrchestratorService, case_id: uuid.UUID) -> int:
    from sqlalchemy import func, select

    return int(
        orch._session.scalar(  # noqa: SLF001
            select(func.count()).select_from(Plan).where(Plan.case_id == case_id)
        )
        or 0
    )


def test_bff_routes_smoke(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
) -> None:
    """Exercise service path used by BFF (HTTP covered lightly via service)."""
    from fastapi.testclient import TestClient

    from app.api.deps import get_app_settings, get_db
    from app.main import app

    def _override_db():
        try:
            yield db_session
        finally:
            pass

    def _override_settings():
        return settings

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_app_settings] = _override_settings
    try:
        client = TestClient(app)
        r = client.post(
            "/api/orchestrator/assess_readiness",
            json={"workspace_id": str(workspace.id), "case_id": str(case.id)},
        )
        assert r.status_code == 200
        assert "ready" in r.json()

        bad = client.post(
            "/api/orchestrator/create_plan",
            json={
                "workspace_id": str(workspace.id),
                "case_id": str(case.id),
                "plan": {"version": 1, "steps": []},
            },
        )
        assert bad.status_code == 422

        good = client.post(
            "/api/orchestrator/create_plan",
            json={
                "workspace_id": str(workspace.id),
                "case_id": str(case.id),
                "plan": VALID_PLAN,
            },
        )
        assert good.status_code == 200
        plan_id = good.json()["plan_id"]

        exec_blocked = client.post(
            "/api/orchestrator/execute_plan",
            json={
                "workspace_id": str(workspace.id),
                "plan_id": plan_id,
                "client_request_id": "http-1",
            },
        )
        assert exec_blocked.status_code == 409

        appr = client.post(
            "/api/orchestrator/approve_plan",
            json={"workspace_id": str(workspace.id), "plan_id": plan_id},
        )
        assert appr.status_code == 200

        ex = client.post(
            "/api/orchestrator/execute_plan",
            json={
                "workspace_id": str(workspace.id),
                "plan_id": plan_id,
                "client_request_id": "http-1",
            },
        )
        assert ex.status_code == 200
        op_id = ex.json()["id"]

        ex2 = client.post(
            "/api/orchestrator/execute_plan",
            json={
                "workspace_id": str(workspace.id),
                "plan_id": plan_id,
                "client_request_id": "http-1",
            },
        )
        assert ex2.status_code == 200
        assert ex2.json()["id"] == op_id

        vr = client.post(
            "/api/orchestrator/verify_result",
            json={"workspace_id": str(workspace.id), "operation_id": op_id},
        )
        assert vr.status_code == 200
        assert vr.json()["state"] == "verified_stub"
    finally:
        app.dependency_overrides.clear()

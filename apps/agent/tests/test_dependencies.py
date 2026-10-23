"""Phase-4 dependencies — discovery, registry honesty, gated create, secrets."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.case import Case
from app.models.workspace import Workspace
from app.services.dependencies import (
    CREATE_DATABASE_CAP,
    CREATE_DISK_CAP,
    DEP_OPEN_NEED_CREATE,
    DEP_OPEN_NEED_INCOMPLETE,
    build_dependency_plan_view,
    can_claim_complete_success,
    discover_dependencies,
    execute_dependency_steps,
)
from app.services.liara_client import LiaraClient
from app.services.orchestrator import ApprovalRequiredError, OrchestratorService
from app.services.registry import CapabilityRegistry
from app.services.secrets import SecretService
from app.services.write_guard import WriteGuard
from app.schemas.orchestration import PlanVersion


@pytest.fixture
def case(db_session: Session, workspace: Workspace) -> Case:
    c = Case(workspace_id=workspace.id, goal="Deps demo", status="open")
    db_session.add(c)
    db_session.flush()
    return c


def _app_with_deps(tmp_path: Path, *, with_redis: bool = True) -> Path:
    pkg: dict = {
        "name": "demo-deps",
        "dependencies": {
            "pg": "^8.0.0",
            "next": "14.0.0",
        },
        "scripts": {"start": "next start -p 3000"},
    }
    if with_redis:
        pkg["dependencies"]["ioredis"] = "^5.0.0"
    (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
    (tmp_path / ".env.example").write_text(
        "DATABASE_URL=postgres://user:secret@localhost/db\n"
        "REDIS_URL=redis://localhost:6379\n"
        "UPLOAD_DIR=/data/uploads\n",
        encoding="utf-8",
    )
    (tmp_path / "liara.json").write_text(
        json.dumps({"disks": [{"name": "data", "mountTo": "/data"}]}),
        encoding="utf-8",
    )
    return tmp_path


def test_discovery_file_backed(tmp_path: Path) -> None:
    root = _app_with_deps(tmp_path)
    discovery = discover_dependencies(root)
    kinds = set(discovery.required_kinds)
    assert "postgres" in kinds
    assert "redis" in kinds
    assert "disk" in kinds
    for finding in discovery.findings:
        assert finding.evidence_paths, "every finding must be file-backed"
        assert any(Path(p).exists() or p.endswith("package.json") or ".env" in p or "liara.json" in p for p in finding.evidence_paths)


def test_discovery_no_signals(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "plain", "scripts": {"start": "node index.js"}, "dependencies": {}}),
        encoding="utf-8",
    )
    discovery = discover_dependencies(tmp_path)
    assert discovery.required_kinds == ()
    assert discovery.notes


def test_plan_view_blocks_complete_when_create_disabled(
    db_session: Session, tmp_path: Path
) -> None:
    registry = CapabilityRegistry(db_session)
    registry.seed()
    assert registry.get(CREATE_DATABASE_CAP).status == "disabled"
    assert registry.get(CREATE_DISK_CAP).status == "disabled"

    discovery = discover_dependencies(_app_with_deps(tmp_path))
    view = build_dependency_plan_view(discovery, registry=registry, project_name="demo")
    assert view.create_database_enabled is False
    assert view.create_disk_enabled is False
    assert DEP_OPEN_NEED_CREATE in view.open_needs
    assert view.can_claim_complete_success is False
    assert view.handoff is not None
    assert view.handoff["reason"] == "ld05_create_unproven"


def test_execute_blocked_without_approval(
    db_session: Session,
    workspace: Workspace,
    case: Case,
    settings: Settings,
    tmp_path: Path,
) -> None:
    svc = OrchestratorService(db_session, settings, write_guard=WriteGuard())
    plan, _ = svc.create_plan(
        workspace_id=workspace.id,
        case_id=case.id,
        deps={"app_path": str(_app_with_deps(tmp_path)), "project_name": "demo"},
    )
    with pytest.raises(ApprovalRequiredError):
        svc.execute_plan(
            workspace_id=workspace.id,
            plan_id=plan.id,
            client_request_id="deps-no-approval",
        )


def test_execute_handoff_when_registry_disabled(
    db_session: Session,
    workspace: Workspace,
    case: Case,
    settings: Settings,
    tmp_path: Path,
) -> None:
    guard = WriteGuard()
    svc = OrchestratorService(db_session, settings, write_guard=guard)
    CapabilityRegistry(db_session).seed()
    plan, validated = svc.create_plan(
        workspace_id=workspace.id,
        case_id=case.id,
        deps={"app_path": str(_app_with_deps(tmp_path)), "project_name": "demo"},
    )
    assert any(s.tool_id in ("create_database", "create_disk") for s in validated.steps)
    svc.approve_plan(workspace_id=workspace.id, plan_id=plan.id)
    op = svc.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="deps-disabled-1",
    )
    assert guard.call_count == 0  # registry gate before WriteGuard
    assert op.state == "handoff"
    cp = op.checkpoint or {}
    assert DEP_OPEN_NEED_CREATE in (cp.get("open_needs") or [])
    assert cp.get("handoff", {}).get("reason") == "ld05_create_unproven"
    assert cp.get("can_claim_complete_success") is False


def _enable_create_tools(registry: CapabilityRegistry) -> None:
    """documented/disabled → documented → tested → enabled for mocked create tests."""
    for tool_id in (CREATE_DATABASE_CAP, CREATE_DISK_CAP):
        cap = registry.get(tool_id)
        if cap.status == "disabled":
            registry.set_status(tool_id, "documented")
        if registry.get(tool_id).status == "documented":
            registry.set_status(tool_id, "tested")
        if registry.get(tool_id).status == "tested":
            registry.set_status(tool_id, "enabled")


def _deps_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method.upper()
        if method == "POST" and path == "/v1/databases":
            return httpx.Response(200, json={"databaseID": "db-created-1"})
        if method == "GET" and path.startswith("/v1/databases/"):
            return httpx.Response(
                200,
                json={
                    "database": {
                        "hostname": "dep-postgres",
                        "username": "root",
                        "dbName": "dep-postgres",
                        "type": "postgresql",
                        "node": {
                            "host": "db.internal",
                            "port": 5432,
                            "root_password": "s3cret-password",
                        },
                    }
                },
            )
        if method == "POST" and path.endswith("/disks"):
            return httpx.Response(201, content=b"")
        if method == "GET" and path.endswith("/disks"):
            return httpx.Response(200, json={"disks": [{"name": "data"}]})
        return httpx.Response(404, json={"message": path})

    return httpx.MockTransport(handler)


def test_mocked_create_stores_secret_ref_no_password_in_checkpoint(
    db_session: Session,
    workspace: Workspace,
    case: Case,
    settings: Settings,
    tmp_path: Path,
) -> None:
    registry = CapabilityRegistry(db_session)
    registry.seed()
    _enable_create_tools(registry)

    client = LiaraClient("test-token", transport=_deps_transport())
    guard = WriteGuard(liara_client=client)
    secrets = SecretService(db_session, settings)
    svc = OrchestratorService(db_session, settings, write_guard=guard)

    # Minimal plan: one postgres create only
    plan, _ = svc.create_plan(
        workspace_id=workspace.id,
        case_id=case.id,
        plan_draft={
            "version": 1,
            "steps": [
                {
                    "id": "dep-pg",
                    "action": "create_database",
                    "tool_id": "create_database",
                    "effects": ["provision_postgres"],
                    "cost_known": False,
                    "params": {
                        "hostname": "dep-postgres",
                        "type": "postgresql",
                        "planID": "small",
                        "version": "16",
                        "publicNetwork": False,
                    },
                }
            ],
            "effects": ["provision_dependencies"],
            "cost_known": False,
            "summary": "create postgres",
        },
    )
    svc.approve_plan(workspace_id=workspace.id, plan_id=plan.id)
    op = svc.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="deps-create-ok",
    )
    assert guard.call_count == 1
    assert op.state == "deps_done"
    cp = op.checkpoint or {}
    blob = json.dumps(cp)
    assert "s3cret-password" not in blob
    assert "postgres://" not in blob or "[redacted]" in blob or "secret_refs" in blob
    refs = (cp.get("provider_ids") or {}).get("secret_refs") or {}
    assert refs
    ref_id = list(refs.values())[0]
    # Secret decryptable internally; public view has no value.
    from uuid import UUID

    value = secrets.get_value(UUID(ref_id))
    assert "s3cret-password" in value
    public = secrets.get_public(UUID(ref_id))
    assert "password" not in public.model_dump()


def test_incomplete_resource_tracked_on_case(
    db_session: Session,
    workspace: Workspace,
    case: Case,
    settings: Settings,
) -> None:
    registry = CapabilityRegistry(db_session)
    registry.seed()
    _enable_create_tools(registry)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method.upper() == "POST" and request.url.path == "/v1/databases":
            # Create succeeds without databaseID → incomplete leftover
            return httpx.Response(200, json={})
        return httpx.Response(404)

    client = LiaraClient("tok", transport=httpx.MockTransport(handler))
    guard = WriteGuard(liara_client=client)
    plan = PlanVersion.model_validate(
        {
            "version": 1,
            "steps": [
                {
                    "id": "dep-pg",
                    "action": "create_database",
                    "tool_id": "create_database",
                    "effects": [],
                    "params": {
                        "hostname": "incomplete-db",
                        "type": "postgresql",
                        "planID": "small",
                        "version": "16",
                    },
                }
            ],
            "effects": [],
        }
    )
    result = execute_dependency_steps(
        plan=plan,
        write_guard=guard,
        registry=registry,
        liara_client=client,
        secrets=SecretService(db_session, settings),
        workspace_id=workspace.id,
        case=case,
        session=db_session,
    )
    assert result.state == "deps_partial"
    assert DEP_OPEN_NEED_INCOMPLETE in result.checkpoint["open_needs"]
    assert result.pending_resources
    db_session.refresh(case)
    pending = (case.constraints or {}).get("pending_resources") or []
    assert pending


def test_verify_blocks_complete_success_with_open_deps(
    db_session: Session,
    workspace: Workspace,
    case: Case,
    settings: Settings,
    tmp_path: Path,
) -> None:
    svc = OrchestratorService(db_session, settings, write_guard=WriteGuard())
    CapabilityRegistry(db_session).seed()
    plan, _ = svc.create_plan(
        workspace_id=workspace.id,
        case_id=case.id,
        deps={"app_path": str(_app_with_deps(tmp_path)), "project_name": "demo"},
    )
    svc.approve_plan(workspace_id=workspace.id, plan_id=plan.id)
    op = svc.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="deps-verify-block",
    )
    verified = svc.verify_result(workspace_id=workspace.id, operation_id=op.id)
    assert verified.state == "blocked"
    assert (verified.checkpoint or {}).get("complete_success") is False


def test_can_claim_complete_success_helper() -> None:
    assert can_claim_complete_success(
        discovery=None, pending_resources=[], open_needs=[]
    )
    assert not can_claim_complete_success(
        discovery=None,
        pending_resources=[{"resource_key": "x"}],
        open_needs=[],
    )
    assert not can_claim_complete_success(
        discovery=None,
        pending_resources=[],
        open_needs=[DEP_OPEN_NEED_CREATE],
    )


def test_discover_api_persists_on_case(
    db_session: Session,
    workspace: Workspace,
    case: Case,
    settings: Settings,
    tmp_path: Path,
) -> None:
    svc = OrchestratorService(db_session, settings)
    payload = svc.discover_dependencies(
        workspace_id=workspace.id,
        case_id=case.id,
        app_path=str(_app_with_deps(tmp_path)),
        project_name="demo",
    )
    assert payload.can_claim_complete_success is False
    assert "postgres" in payload.discovery.required_kinds
    db_session.refresh(case)
    assert (case.constraints or {}).get("dependency_plan")

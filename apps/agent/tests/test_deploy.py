"""Phase-1 deploy — approval gate, mocked Liara writes, timeout reconcile."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.case import Case
from app.models.workspace import Workspace
from app.services.deploy import build_node_next_plan, promote_deploy_tools_tested
from app.services.liara_client import LiaraClient
from app.services.orchestrator import ApprovalRequiredError, OrchestratorService
from app.services.registry import CapabilityRegistry
from app.services.write_guard import WriteGuard


def _archive(tmp_path: Path) -> Path:
    path = tmp_path / "source.tar.gz"
    path.write_bytes(b"\x1f\x8bfake-gz-payload")
    return path


def _mock_deploy_transport(
    *,
    timeout_on: str | None = None,
    project_exists_on_get: bool = False,
) -> httpx.MockTransport:
    """Simulate create → sources → releases; optional timeout + GET reconcile."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method.upper()

        if timeout_on and method == "POST":
            if timeout_on == "create" and path == "/v1/projects":
                raise httpx.ReadTimeout("slow create", request=request)
            if timeout_on == "sources" and path.endswith("/sources"):
                raise httpx.ReadTimeout("slow sources", request=request)
            if timeout_on == "releases" and path.endswith("/releases"):
                raise httpx.ReadTimeout("slow releases", request=request)

        if method == "GET" and path == "/v1/networks":
            return httpx.Response(
                200,
                json={"networks": [{"_id": "net-mock-1", "name": "companion-net"}]},
            )
        if method == "GET" and path == "/v1/me":
            return httpx.Response(
                200,
                json={
                    "plans": {
                        "projectBundlePlans": {
                            "free": {"free": {"available": True, "displayPrice": 0}},
                            "small-g2": {
                                "basic": {"available": True, "displayPrice": 1}
                            },
                        }
                    }
                },
            )
        if method == "POST" and path == "/v1/projects":
            return httpx.Response(200, content=b"")
        if method == "POST" and path.endswith("/sources"):
            return httpx.Response(200, json={"sourceID": "src-mock-1"})
        if method == "POST" and path.endswith("/releases"):
            return httpx.Response(200, json={"releaseID": "rel-mock-1"})
        if method == "GET" and "/releases" in path:
            return httpx.Response(
                200,
                json={
                    "total": 1,
                    "currentRelease": "rel-mock-1",
                    "releases": [
                        {"_id": "rel-mock-1", "state": "READY", "port": 3000}
                    ],
                },
            )
        if method == "GET" and path.startswith("/v1/projects/"):
            if project_exists_on_get or timeout_on != "create":
                name = path.rsplit("/", 1)[-1]
                return httpx.Response(
                    200,
                    json={
                        "project": {
                            "project_id": name,
                            "status": "RUNNING",
                            "isDeployed": True,
                        }
                    },
                )
            return httpx.Response(404, json={"message": "missing"})
        return httpx.Response(404, json={"message": f"unhandled {method} {path}"})

    return httpx.MockTransport(handler)


@pytest.fixture
def case(db_session: Session, workspace: Workspace) -> Case:
    c = Case(workspace_id=workspace.id, goal="Deploy demo", status="open")
    db_session.add(c)
    db_session.flush()
    return c


def test_no_approval_zero_liara_http(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
    tmp_path: Path,
) -> None:
    archive = _archive(tmp_path)
    http_posts: list[str] = []

    def counting(request: httpx.Request) -> httpx.Response:
        if request.method.upper() == "POST":
            http_posts.append(request.url.path)
        return httpx.Response(500)

    client = LiaraClient(
        "tok", transport=httpx.MockTransport(counting), timeout=1.0
    )
    guard = WriteGuard(liara_client=client)
    orch = OrchestratorService(
        db_session, settings, write_guard=guard, liara_client=client
    )
    plan_body = build_node_next_plan(
        project_name="demo-no-appr",
        archive_path=str(archive),
        port=3000,
    )
    plan, _ = orch.create_plan(
        workspace_id=workspace.id, case_id=case.id, plan_draft=plan_body
    )
    with pytest.raises(ApprovalRequiredError):
        orch.execute_plan(
            workspace_id=workspace.id,
            plan_id=plan.id,
            client_request_id="no-appr",
        )
    assert guard.call_count == 0
    assert http_posts == []


def test_approved_mock_deploy_records_ids(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
    tmp_path: Path,
) -> None:
    archive = _archive(tmp_path)
    client = LiaraClient(
        "tok", transport=_mock_deploy_transport(), timeout=5.0
    )
    guard = WriteGuard(liara_client=client)
    orch = OrchestratorService(
        db_session, settings, write_guard=guard, liara_client=client
    )
    plan_body = build_node_next_plan(
        project_name="demo-happy",
        archive_path=str(archive),
        port=3000,
        platform="node",
    )
    plan, _ = orch.create_plan(
        workspace_id=workspace.id, case_id=case.id, plan_draft=plan_body
    )
    orch.approve_plan(workspace_id=workspace.id, plan_id=plan.id)
    op = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="happy-1",
        promote_registry_on_success=True,
    )
    assert guard.call_count == 3
    assert guard.http_call_count == 3
    assert op.state == "deployed"
    ids = (op.checkpoint or {}).get("provider_ids") or {}
    assert ids.get("sourceID") == "src-mock-1"
    assert ids.get("releaseID") == "rel-mock-1"
    assert ids.get("project_name") == "demo-happy"

    verified = orch.verify_result(
        workspace_id=workspace.id,
        operation_id=op.id,
        http_get=lambda _url: 200,
        app_url="https://demo-happy.liara.run",
    )
    assert verified.state == "verified"
    assert (verified.checkpoint or {}).get("verification", {}).get("release_ok")

    registry = CapabilityRegistry(db_session)
    assert registry.get("create_project").status == "tested"
    assert registry.get("sources_releases").status == "tested"


def test_timeout_marks_unknown_reconcile_no_blind_retry(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
    tmp_path: Path,
) -> None:
    archive = _archive(tmp_path)
    create_posts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal create_posts
        method = request.method.upper()
        path = request.url.path
        if method == "GET" and path == "/v1/networks":
            return httpx.Response(
                200,
                json={"networks": [{"_id": "net-mock-1", "name": "companion-net"}]},
            )
        if method == "GET" and path == "/v1/me":
            return httpx.Response(
                200,
                json={
                    "plans": {
                        "projectBundlePlans": {
                            "free": {"free": {"available": True, "displayPrice": 0}}
                        }
                    }
                },
            )
        if method == "POST" and path == "/v1/projects":
            create_posts += 1
            raise httpx.ReadTimeout("slow", request=request)
        if method == "POST" and path.endswith("/sources"):
            return httpx.Response(200, json={"sourceID": "src-after-reconcile"})
        if method == "POST" and path.endswith("/releases"):
            return httpx.Response(200, json={"releaseID": "rel-after-reconcile"})
        if method == "GET" and path.endswith("/releases"):
            return httpx.Response(200, json={"releases": [], "total": 0})
        if method == "GET" and path.startswith("/v1/projects/"):
            name = path.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={
                    "project": {
                        "project_id": name,
                        "status": "RUNNING",
                        "isDeployed": False,
                    }
                },
            )
        return httpx.Response(404)

    client = LiaraClient("tok", transport=httpx.MockTransport(handler), timeout=0.5)
    guard = WriteGuard(liara_client=client)
    orch = OrchestratorService(
        db_session, settings, write_guard=guard, liara_client=client
    )
    plan_body = build_node_next_plan(
        project_name="demo-timeout",
        archive_path=str(archive),
    )
    plan, _ = orch.create_plan(
        workspace_id=workspace.id, case_id=case.id, plan_draft=plan_body
    )
    orch.approve_plan(workspace_id=workspace.id, plan_id=plan.id)
    op = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="timeout-1",
    )
    assert op.state == "unknown"
    assert create_posts == 1
    attempts = (op.checkpoint or {}).get("attempts") or []
    assert attempts
    assert attempts[0]["status"] in ("unknown", "reconciled")
    assert (op.checkpoint or {}).get("provider_ids", {}).get("project_exists") is True

    # Duplicate client_request_id — no second create.
    op2 = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="timeout-1",
    )
    assert op2.id == op.id
    assert create_posts == 1

    # New request id with prior unknown → skip create (project_exists), no blind POST.
    op3 = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="timeout-retry-2",
    )
    assert create_posts == 1  # still no second create
    attempts3 = (op3.checkpoint or {}).get("attempts") or []
    create_attempt = next(a for a in attempts3 if a["step_id"] == "create-project")
    assert create_attempt["status"] == "skipped"


def test_duplicate_client_request_id_no_rewrite(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
    tmp_path: Path,
) -> None:
    archive = _archive(tmp_path)
    client = LiaraClient("tok", transport=_mock_deploy_transport(), timeout=5.0)
    guard = WriteGuard(liara_client=client)
    orch = OrchestratorService(
        db_session, settings, write_guard=guard, liara_client=client
    )
    plan_body = build_node_next_plan(
        project_name="demo-idem", archive_path=str(archive)
    )
    plan, _ = orch.create_plan(
        workspace_id=workspace.id, case_id=case.id, plan_draft=plan_body
    )
    orch.approve_plan(workspace_id=workspace.id, plan_id=plan.id)
    op1 = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="idem-deploy",
    )
    calls = guard.call_count
    op2 = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="idem-deploy",
    )
    assert op1.id == op2.id
    assert guard.call_count == calls


def test_assess_readiness_uses_node_adapter(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "node_app_missing"
    orch = OrchestratorService(db_session, settings, write_guard=WriteGuard())
    assessment = orch.assess_readiness(
        workspace_id=workspace.id,
        case_id=case.id,
        app_path=str(fixture),
    )
    assert assessment.ready is False
    assert assessment.platform == "next"
    codes = {f.code for f in assessment.findings}
    assert "missing_port" in codes
    assert "missing_start_script" in codes


def test_promote_deploy_tools_idempotent(db_session: Session) -> None:
    registry = CapabilityRegistry(db_session)
    registry.seed()
    first = promote_deploy_tools_tested(registry)
    assert "create_project" in first
    second = promote_deploy_tools_tested(registry)
    assert second == []

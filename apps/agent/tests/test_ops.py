"""Phase-2 ops — env contract, restart/resize, domain/ssl, DNS handoff, resume."""

from __future__ import annotations

import json

import httpx
import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.case import Case
from app.models.workspace import Workspace
from app.services.liara_client import LiaraClient
from app.services.ops import (
    ENV_CONTRACT_PROVEN,
    ENV_OPEN_NEED,
    build_domain_ssl_plan,
    build_env_diff,
    build_env_update_plan,
    build_restart_plan,
    build_resize_plan,
    characterize_env_provider_semantics,
    classify_domain_ssl_state,
    ensure_update_envs_disabled,
    promote_ops_tools_tested,
    zone_owned,
)
from app.services.orchestrator import ApprovalRequiredError, OrchestratorService
from app.services.registry import CapabilityRegistry
from app.services.write_guard import WriteGuard, WriteNotAllowlisted


@pytest.fixture
def case(db_session: Session, workspace: Workspace) -> Case:
    c = Case(workspace_id=workspace.id, goal="Ops demo", status="open")
    db_session.add(c)
    db_session.flush()
    return c


def _ops_transport(
    *,
    cert_status: str = "PENDING",
    zones: list[dict] | None = None,
    env_mode: str = "replace",
) -> httpx.MockTransport:
    """Mock PaaS + DNS hosts used by phase-2 client methods."""
    store: dict[str, list[str]] = {"demo-app": ["KEEP", "OLD"]}

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        path = request.url.path
        method = request.method.upper()

        # DNS service
        if "dns-service" in host:
            if method == "GET" and path == "/api/v1/zones":
                return httpx.Response(
                    200, json={"zones": zones if zones is not None else []}
                )
            if method == "POST" and "/dns-records" in path:
                return httpx.Response(
                    201, json={"status": "success", "data": {"id": "rec-1"}}
                )
            return httpx.Response(404, json={"message": f"dns {path}"})

        if method == "POST" and path.endswith("/actions/restart"):
            return httpx.Response(200, content=b"")
        if method == "POST" and path.endswith("/resize"):
            return httpx.Response(200, content=b"")
        if method == "POST" and path == "/v1/domains":
            return httpx.Response(201, json={"domain": {"_id": "dom-1"}})
        if method == "POST" and path == "/v1/domains/provision-ssl-certs":
            return httpx.Response(200, json={"code": "ACCEPTED"})
        if method == "GET" and path.startswith("/v1/domains/") and path.endswith(
            "/check"
        ):
            return httpx.Response(
                200,
                json={
                    "domain": {
                        "_id": "dom-1",
                        "name": "example.com",
                        "status": "ACTIVE",
                        "certificatesStatus": cert_status,
                    }
                },
            )
        if method == "POST" and path == "/v1/projects/update-envs":
            body = json.loads(request.content.decode() or "{}")
            project = body.get("project", "demo-app")
            keys = [v["key"] for v in body.get("variables", [])]
            if env_mode == "replace":
                store[project] = list(keys)
            else:
                merged = set(store.get(project, [])) | set(keys)
                store[project] = sorted(merged)
            return httpx.Response(200, json={"message": "ok"})
        if method == "GET" and path.startswith("/v1/projects/"):
            name = path.rsplit("/", 1)[-1]
            if name == "releases":
                return httpx.Response(200, json={"releases": [], "total": 0})
            envs = [{"key": k, "value": "x"} for k in store.get(name, [])]
            return httpx.Response(
                200,
                json={
                    "project": {
                        "project_id": name,
                        "status": "RUNNING",
                        "isDeployed": True,
                        "envs": envs,
                    }
                },
            )
        return httpx.Response(404, json={"message": f"unhandled {method} {path}"})

    return httpx.MockTransport(handler)


def test_env_contract_unproven_flag() -> None:
    assert ENV_CONTRACT_PROVEN is False


def test_env_diff_redacts_values_and_blocks_write() -> None:
    diff = build_env_diff(
        project="demo-app",
        baseline_envs=[
            {"key": "KEEP", "value": "secret-a"},
            {"key": "OLD", "value": "secret-b"},
        ],
        proposed=[{"key": "KEEP", "value": "new"}, {"key": "NEW", "value": "x"}],
    )
    dumped = diff.to_dict()
    blob = json.dumps(dumped)
    assert "secret" not in blob
    assert dumped["writable"] is False
    assert dumped["open_need"] == ENV_OPEN_NEED
    assert dumped["added_keys"] == ["NEW"]
    assert dumped["changed_keys"] == ["KEEP"]
    assert dumped["removed_keys"] == ["OLD"]


def test_characterize_merge_vs_replace_on_mock_semantics() -> None:
    assert (
        characterize_env_provider_semantics(
            baseline_keys=["KEEP", "OLD"],
            sent_keys=["KEEP", "NEW"],
            after_keys=["KEEP", "NEW"],
        )
        == "replace"
    )
    assert (
        characterize_env_provider_semantics(
            baseline_keys=["KEEP", "OLD"],
            sent_keys=["KEEP", "NEW"],
            after_keys=["KEEP", "OLD", "NEW"],
        )
        == "merge"
    )


def test_update_envs_not_allowlisted() -> None:
    guard = WriteGuard()
    with pytest.raises(WriteNotAllowlisted):
        guard.execute_allowlisted(
            tool_id="update_envs",
            payload={"project": "x", "variables": [{"key": "A", "value": "1"}]},
        )


def test_env_execute_blocked_with_approval_zero_http(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
) -> None:
    posts: list[str] = []

    def counting(request: httpx.Request) -> httpx.Response:
        if request.method.upper() == "POST":
            posts.append(request.url.path)
        return httpx.Response(200, json={"project": {"envs": [], "status": "RUNNING"}})

    client = LiaraClient("tok", transport=httpx.MockTransport(counting), timeout=2.0)
    guard = WriteGuard(liara_client=client)
    orch = OrchestratorService(
        db_session, settings, write_guard=guard, liara_client=client
    )
    plan_body = build_env_update_plan(
        project_name="demo-app",
        variables=[{"key": "FOO", "value": "bar"}],
    )
    plan, _ = orch.create_plan(
        workspace_id=workspace.id, case_id=case.id, plan_draft=plan_body
    )
    orch.approve_plan(workspace_id=workspace.id, plan_id=plan.id)
    op = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="env-blocked-1",
        promote_registry_on_success=True,
    )
    assert op.state == "ops_blocked"
    assert ENV_OPEN_NEED in (op.checkpoint or {}).get("open_needs", [])
    assert (op.checkpoint or {}).get("env_diff", {}).get("writable") is False
    assert not any("update-envs" in p for p in posts)
    assert guard.http_call_count == 0

    registry = CapabilityRegistry(db_session)
    registry.seed()
    assert registry.get("update_envs").status == "disabled"


def test_restart_requires_approval(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
) -> None:
    client = LiaraClient(
        "tok", transport=_ops_transport(), timeout=2.0
    )
    guard = WriteGuard(liara_client=client)
    orch = OrchestratorService(
        db_session, settings, write_guard=guard, liara_client=client
    )
    plan, _ = orch.create_plan(
        workspace_id=workspace.id,
        case_id=case.id,
        plan_draft=build_restart_plan(project_name="demo-app", reason="stuck"),
    )
    with pytest.raises(ApprovalRequiredError):
        orch.execute_plan(
            workspace_id=workspace.id,
            plan_id=plan.id,
            client_request_id="restart-no-appr",
        )
    assert guard.call_count == 0


def test_restart_and_resize_with_health_mock(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
) -> None:
    client = LiaraClient("tok", transport=_ops_transport(), timeout=2.0)
    guard = WriteGuard(liara_client=client)
    orch = OrchestratorService(
        db_session, settings, write_guard=guard, liara_client=client
    )

    restart_plan, _ = orch.create_plan(
        workspace_id=workspace.id,
        case_id=case.id,
        ops={"kind": "restart", "project_name": "demo-app"},
    )
    orch.approve_plan(workspace_id=workspace.id, plan_id=restart_plan.id)
    op = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=restart_plan.id,
        client_request_id="restart-ok",
        promote_registry_on_success=True,
    )
    assert op.state == "ops_done"
    assert (op.checkpoint or {}).get("health", {}).get("healthy") is True
    assert guard.http_call_count >= 1

    resize_body = build_resize_plan(project_name="demo-app", plan_id="standard")
    assert resize_body["cost_known"] is False
    assert "unknown" in (resize_body.get("cost_summary") or "")
    resize_plan, _ = orch.create_plan(
        workspace_id=workspace.id, case_id=case.id, plan_draft=resize_body
    )
    orch.approve_plan(workspace_id=workspace.id, plan_id=resize_plan.id)
    op2 = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=resize_plan.id,
        client_request_id="resize-ok",
        promote_registry_on_success=True,
    )
    assert op2.state == "ops_done"
    assert (op2.checkpoint or {}).get("provider_ids", {}).get("cost_known") is False

    registry = CapabilityRegistry(db_session)
    registry.seed()
    promote_ops_tools_tested(registry)
    assert registry.get("restart_resize").status == "tested"
    assert registry.get("update_envs").status == "disabled"


def test_domain_ssl_distinguishes_acceptance_vs_cert(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
) -> None:
    client = LiaraClient(
        "tok", transport=_ops_transport(cert_status="PENDING"), timeout=2.0
    )
    guard = WriteGuard(liara_client=client)
    orch = OrchestratorService(
        db_session, settings, write_guard=guard, liara_client=client
    )
    plan, _ = orch.create_plan(
        workspace_id=workspace.id,
        case_id=case.id,
        plan_draft=build_domain_ssl_plan(
            project_name="demo-app", domain_name="example.com"
        ),
    )
    orch.approve_plan(workspace_id=workspace.id, plan_id=plan.id)
    op = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="domain-ssl-1",
        promote_registry_on_success=True,
    )
    ds = (op.checkpoint or {}).get("domain_status") or {}
    assert ds.get("ssl_request_accepted") is True
    assert ds.get("cert_valid") is False
    assert (op.checkpoint or {}).get("provider_ids", {}).get("ssl_cert_valid") is False

    valid = classify_domain_ssl_state(
        ssl_request_accepted=True,
        certificates_status="ACTIVE",
        domain_status="ACTIVE",
    )
    assert valid["cert_valid"] is True
    assert valid["ssl_complete"] is True


def test_dns_handoff_when_zone_not_owned(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
) -> None:
    client = LiaraClient(
        "tok",
        transport=_ops_transport(zones=[{"name": "other.com"}]),
        timeout=2.0,
    )
    guard = WriteGuard(liara_client=client)
    orch = OrchestratorService(
        db_session, settings, write_guard=guard, liara_client=client
    )
    plan_body = {
        "version": 1,
        "steps": [
            {
                "id": "dns",
                "action": "create_dns_record",
                "tool_id": "dns_create_record",
                "effects": ["create_dns_record"],
                "cost_known": False,
                "params": {
                    "zone": "example.com",
                    "name": "@",
                    "type": "A",
                    "contents": [{"ip": "1.2.3.4"}],
                    "ttl": 3600,
                },
            }
        ],
        "effects": ["create_dns_record"],
        "cost_known": False,
        "summary": "dns handoff",
    }
    plan, _ = orch.create_plan(
        workspace_id=workspace.id, case_id=case.id, plan_draft=plan_body
    )
    orch.approve_plan(workspace_id=workspace.id, plan_id=plan.id)
    before = guard.http_call_count
    op = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="dns-handoff-1",
    )
    assert op.state == "handoff"
    assert (op.checkpoint or {}).get("handoff", {}).get("reason") == "zone_not_owned"
    assert guard.http_call_count == before  # no DNS write
    assert zone_owned([{"name": "example.com"}], "example.com") is True


def test_dns_write_when_zone_owned(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
) -> None:
    client = LiaraClient(
        "tok",
        transport=_ops_transport(zones=[{"name": "example.com"}]),
        timeout=2.0,
    )
    guard = WriteGuard(liara_client=client)
    orch = OrchestratorService(
        db_session, settings, write_guard=guard, liara_client=client
    )
    plan_body = {
        "version": 1,
        "steps": [
            {
                "id": "dns",
                "action": "create_dns_record",
                "tool_id": "dns_create_record",
                "effects": ["create_dns_record"],
                "cost_known": False,
                "params": {
                    "zone": "example.com",
                    "name": "@",
                    "type": "A",
                    "contents": [{"ip": "1.2.3.4"}],
                },
            }
        ],
        "effects": ["create_dns_record"],
        "cost_known": False,
        "summary": "dns owned",
    }
    plan, _ = orch.create_plan(
        workspace_id=workspace.id, case_id=case.id, plan_draft=plan_body
    )
    orch.approve_plan(workspace_id=workspace.id, plan_id=plan.id)
    op = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="dns-owned-1",
        promote_registry_on_success=True,
    )
    assert op.state == "ops_done"
    assert (op.checkpoint or {}).get("provider_ids", {}).get("dns_record_id") == "rec-1"


def test_resume_loads_operation_no_duplicate_write(
    db_session: Session,
    settings: Settings,
    workspace: Workspace,
    case: Case,
) -> None:
    client = LiaraClient("tok", transport=_ops_transport(), timeout=2.0)
    guard = WriteGuard(liara_client=client)
    orch = OrchestratorService(
        db_session, settings, write_guard=guard, liara_client=client
    )
    plan, _ = orch.create_plan(
        workspace_id=workspace.id,
        case_id=case.id,
        ops={"kind": "restart", "project_name": "demo-app"},
    )
    orch.approve_plan(workspace_id=workspace.id, plan_id=plan.id)
    op = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="resume-req-1",
    )
    writes_after_exec = guard.call_count

    # Simulate session/worker restart: new service instance, same DB session.
    orch2 = OrchestratorService(
        db_session, settings, write_guard=guard, liara_client=client
    )
    resumed = orch2.resume_operation(
        workspace_id=workspace.id, operation_id=op.id
    )
    assert resumed.id == op.id
    assert resumed.client_request_id == "resume-req-1"
    assert (resumed.checkpoint or {}).get("resume", {}).get("duplicate_write") is False
    assert guard.call_count == writes_after_exec

    # Idempotent execute with same client_request_id also skips write.
    again = orch2.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id="resume-req-1",
    )
    assert again.id == op.id
    assert guard.call_count == writes_after_exec

    by_crid = orch2.get_operation(
        workspace_id=workspace.id, client_request_id="resume-req-1"
    )
    assert by_crid.id == op.id


def test_seed_update_envs_disabled(db_session: Session) -> None:
    registry = CapabilityRegistry(db_session)
    registry.seed()
    assert registry.get("update_envs").status == "disabled"
    assert ensure_update_envs_disabled(registry) == "disabled"

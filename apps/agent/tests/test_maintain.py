"""Phase-6 maintain — monitor≠write, recovery needs approval, viewer denied, stale data."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.case import Case
from app.models.maintain import RecoveryBaseline
from app.models.workspace import Workspace
from app.services.maintain import (
    DOCUMENTED_ADAPTER_TOOL_IDS,
    MaintainService,
    STALE_AFTER_MISSES,
    ensure_documented_adapters,
    monitor_to_status,
    sanitize_for_audit,
)
from app.services.orchestrator import (
    ApprovalRequiredError,
    OrchestratorService,
    RoleForbiddenError,
)
from app.services.registry import CapabilityRegistry
from app.services.roles import ROLE_OWNER, ROLE_VIEWER, RolesService
from app.services.write_guard import WriteGuard


@pytest.fixture
def case(db_session: Session, workspace: Workspace) -> Case:
    c = Case(workspace_id=workspace.id, goal="Maintain demo", status="open")
    db_session.add(c)
    db_session.flush()
    return c


def test_sanitize_audit_redacts_secrets() -> None:
    clean = sanitize_for_audit(
        {
            "project": "demo",
            "liara_api_token": "super-secret-token-value",
            "nested": {"password": "x", "ok": 1},
        }
    )
    assert clean["project"] == "demo"
    assert clean["liara_api_token"] == "[redacted]"
    assert clean["nested"]["password"] == "[redacted]"
    assert clean["nested"]["ok"] == 1


def test_monitor_enable_does_not_authorize_writes(
    db_session: Session, workspace: Workspace, case: Case, settings: Settings
) -> None:
    orch = OrchestratorService(db_session, settings, write_guard=WriteGuard())
    status = orch.enable_monitor(
        workspace_id=workspace.id,
        target="demo-app",
        case_id=case.id,
        interval_seconds=30,
    )
    assert status.enabled is True
    assert status.grants_write_permission is False

    # Alert path — still no write auth; WriteGuard untouched.
    writes_before = orch.write_guard.call_count

    def alert_check(monitor):  # noqa: ANN001
        return {
            "ok": False,
            "status": "alert",
            "message": "health down",
            "code": "http_5xx",
            "data_received": True,
        }

    out = orch.run_monitor_check(
        workspace_id=workspace.id,
        monitor_id=uuid.UUID(status.monitor_id),
        check_fn=alert_check,
    )
    assert out["monitor_grants_write"] is False
    assert out["incident_grants_write"] is False
    assert out["incident"] is not None
    assert out["incident"]["write_authorized"] is False
    assert out["incident"]["alert_count"] == 1
    assert orch.write_guard.call_count == writes_before

    # Dedupe: second alert bumps same incident.
    out2 = orch.run_monitor_check(
        workspace_id=workspace.id,
        monitor_id=uuid.UUID(status.monitor_id),
        check_fn=alert_check,
    )
    assert out2["incident"]["incident_id"] == out["incident"]["incident_id"]
    assert out2["incident"]["alert_count"] == 2
    assert out2["incident"]["write_authorized"] is False


def test_stale_monitor_data_not_live_healthy(
    db_session: Session, workspace: Workspace, case: Case
) -> None:
    svc = MaintainService(db_session)
    mon = svc.enable_monitor(
        workspace_id=workspace.id, target="stale-app", case_id=case.id
    )

    def miss(_monitor):  # noqa: ANN001
        return {"ok": False, "status": "error", "data_received": False}

    svc_miss = MaintainService(db_session, periodic_check=miss)
    for _ in range(STALE_AFTER_MISSES):
        mon, _inc = svc_miss.run_periodic_check(
            workspace_id=workspace.id, monitor_id=mon.id
        )

    status = monitor_to_status(mon)
    assert status.stale is True
    assert status.healthy_live is False
    assert status.last_status == "stale"
    assert status.grants_write_permission is False


def test_recovery_requires_fresh_approval(
    db_session: Session, workspace: Workspace, case: Case, settings: Settings
) -> None:
    orch = OrchestratorService(db_session, settings, write_guard=WriteGuard())
    MaintainService(db_session).capture_baseline(
        workspace_id=workspace.id,
        project_name="demo-app",
        case_id=case.id,
        snapshot={"project_name": "demo-app", "platform": "node", "port": 3000},
    )

    plan, _validated, view = orch.create_recovery_plan(
        workspace_id=workspace.id,
        case_id=case.id,
        project_name="demo-app",
        action="restart",
    )
    assert view.requires_fresh_approval is True
    assert view.monitor_enable_authorizes is False
    assert view.incident_alert_authorizes is False

    writes_before = orch.write_guard.call_count
    with pytest.raises(ApprovalRequiredError):
        orch.execute_plan(
            workspace_id=workspace.id,
            plan_id=plan.id,
            client_request_id=f"rec-{uuid.uuid4().hex[:8]}",
        )
    assert orch.write_guard.call_count == writes_before

    # Fresh approval then execute is allowed (noop write guard).
    orch.approve_plan(workspace_id=workspace.id, plan_id=plan.id)
    op = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id=f"rec-ok-{uuid.uuid4().hex[:8]}",
    )
    assert op.state is not None
    # Baseline captured again on write path.
    baselines = list(
        db_session.scalars(
            select(RecoveryBaseline).where(
                RecoveryBaseline.workspace_id == workspace.id,
                RecoveryBaseline.project_name == "demo-app",
            )
        ).all()
    )
    assert len(baselines) >= 1


def test_viewer_cannot_execute_writes(
    db_session: Session, workspace: Workspace, case: Case, settings: Settings
) -> None:
    roles = RolesService(db_session)
    roles.upsert_member(
        workspace_id=workspace.id, actor_id="owner-1", role=ROLE_OWNER
    )
    roles.upsert_member(
        workspace_id=workspace.id, actor_id="viewer-1", role=ROLE_VIEWER
    )

    orch = OrchestratorService(db_session, settings, write_guard=WriteGuard())
    plan, _ = orch.create_plan(
        workspace_id=workspace.id,
        case_id=case.id,
        plan_draft={
            "version": 1,
            "steps": [
                {
                    "id": "r1",
                    "action": "restart",
                    "tool_id": "restart",
                    "effects": ["restart"],
                    "params": {"project_name": "demo-app"},
                }
            ],
            "effects": ["restart"],
            "cost_known": True,
            "summary": "restart",
        },
    )
    orch.approve_plan(workspace_id=workspace.id, plan_id=plan.id)

    writes_before = orch.write_guard.call_count
    with pytest.raises(RoleForbiddenError) as exc:
        orch.execute_plan(
            workspace_id=workspace.id,
            plan_id=plan.id,
            client_request_id=f"viewer-{uuid.uuid4().hex[:8]}",
            actor_id="viewer-1",
        )
    assert exc.value.code == "role_denied"
    assert orch.write_guard.call_count == writes_before

    # Owner may execute.
    op = orch.execute_plan(
        workspace_id=workspace.id,
        plan_id=plan.id,
        client_request_id=f"owner-{uuid.uuid4().hex[:8]}",
        actor_id="owner-1",
    )
    assert op.id is not None


def test_resolve_incident_requires_evidence(
    db_session: Session, workspace: Workspace, case: Case, settings: Settings
) -> None:
    orch = OrchestratorService(db_session, settings, write_guard=WriteGuard())
    status = orch.enable_monitor(
        workspace_id=workspace.id, target="demo-app", case_id=case.id
    )

    def alert_check(_m):  # noqa: ANN001
        return {
            "ok": False,
            "status": "alert",
            "message": "down",
            "code": "down",
            "data_received": True,
        }

    out = orch.run_monitor_check(
        workspace_id=workspace.id,
        monitor_id=uuid.UUID(status.monitor_id),
        check_fn=alert_check,
    )
    card = orch.resolve_incident(
        workspace_id=workspace.id,
        incident_id=uuid.UUID(out["incident"]["incident_id"]),
        evidence="HTTP 200 for 3 consecutive checks",
    )
    assert card.status == "resolved"
    assert card.write_authorized is False
    assert card.resolve_evidence


def test_audit_list_sanitized(
    db_session: Session, workspace: Workspace, case: Case, settings: Settings
) -> None:
    orch = OrchestratorService(db_session, settings, write_guard=WriteGuard())
    orch.enable_monitor(
        workspace_id=workspace.id, target="demo-app", case_id=case.id
    )
    events = orch.list_audit_events(workspace_id=workspace.id, case_id=case.id)
    assert events
    blob = str(events)
    assert "super-secret" not in blob
    assert any(e["event_type"].startswith("maintain.") for e in events)


def test_documented_only_adapters_in_registry(db_session: Session) -> None:
    registry = CapabilityRegistry(db_session)
    found = ensure_documented_adapters(registry)
    assert DOCUMENTED_ADAPTER_TOOL_IDS.issubset(set(found))
    for tool_id in DOCUMENTED_ADAPTER_TOOL_IDS:
        assert registry.get(tool_id).status == "documented"

"""Phase-5 code patch + sandbox — separate approvals, scrub secrets, no auto-release."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.workspace import Workspace
from app.services.orchestrator import OrchestratorError, OrchestratorService
from app.services.patch import (
    APPROVAL_KIND_PATCH_RECORD,
    APPROVAL_KIND_RELEASE,
    assert_env_scrubbed,
    build_fixture_fix_diff,
    scrub_env,
)
from app.services.registry import CapabilityRegistry
from app.services.write_guard import WriteGuard

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "patch_app"

# Comment-only diff — applies cleanly but leaves the arithmetic bug (tests stay red).
RED_DIFF = """\
--- a/calc.py
+++ b/calc.py
@@ -2,5 +2,5 @@
 
 
 def add(a: int, b: int) -> int:
-    # Intentional bug: subtract instead of add (fixed by sandbox patch).
+    # Intentional bug: still broken (noop patch for red sandbox).
     return a - b
"""


def _seed_evidence_diagnosis(
    svc: OrchestratorService, workspace: Workspace
) -> tuple[object, str, str]:
    case = svc.ensure_case(workspace_id=workspace.id, goal="fix arithmetic bug")
    from datetime import datetime, timezone

    from app.schemas.orchestration import (
        Diagnosis,
        EvidenceFact,
        EvidencePack,
        Hypothesis,
    )

    suffix = case.id.hex[:8]
    ev = EvidencePack(
        version=f"evidence-patch-{suffix}-xx",
        project_name="fixture-patch",
        symptom="add returns wrong value",
        collected_at=datetime.now(timezone.utc).isoformat(),
        facts=[
            EvidenceFact(
                id="f1",
                source="logs",
                summary="AssertionError: assert -1 == 5 in test_add",
            )
        ],
        gaps=[],
        complete=True,
    )
    diag = Diagnosis(
        version=f"diagnosis-patch-{suffix}-xx",
        evidence_version=ev.version,
        created_at=datetime.now(timezone.utc).isoformat(),
        facts=ev.facts,
        hypotheses=[
            Hypothesis(
                id="h1",
                rank=1,
                statement="calc.add subtracts instead of adds",
                supporting_fact_ids=["f1"],
            )
        ],
        data_gaps=[],
        summary="Limited code defect in calc.add",
        insufficient_evidence=False,
    )
    store = svc._case_store(case)  # noqa: SLF001
    store["evidence"] = {ev.version: ev.model_dump(mode="json")}
    store["latest_evidence_version"] = ev.version
    store["diagnoses"] = {diag.version: diag.model_dump(mode="json")}
    store["latest_diagnosis_version"] = diag.version
    svc._save_case_store(case, store)  # noqa: SLF001
    return case, ev.version, diag.version


@pytest.fixture
def orch(db_session: Session, settings: Settings) -> OrchestratorService:
    guard = WriteGuard()
    return OrchestratorService(db_session, settings, write_guard=guard)


def test_scrub_env_removes_master_key_and_prod_token() -> None:
    polluted = {
        "PATH": "/usr/bin",
        "SECRETS_MASTER_KEY": "should-not-leak",
        "LIARA_API_TOKEN": "prod-token-value",
        "LLM_API_KEY": "llm-secret",
        "SAFE_FLAG": "ok",
        "MY_CUSTOM_TOKEN": "also-gone",
    }
    cleaned = scrub_env(polluted)
    assert "SECRETS_MASTER_KEY" not in cleaned
    assert "LIARA_API_TOKEN" not in cleaned
    assert "LLM_API_KEY" not in cleaned
    assert "MY_CUSTOM_TOKEN" not in cleaned
    assert cleaned.get("SAFE_FLAG") == "ok"
    assert assert_env_scrubbed(cleaned) == []


def test_create_patch_and_sandbox_green_with_isolation(
    orch: OrchestratorService, workspace: Workspace
) -> None:
    case, ev_v, diag_v = _seed_evidence_diagnosis(orch, workspace)
    writes_before = orch.write_guard.call_count

    payload = orch.create_patch(
        workspace_id=workspace.id,
        case_id=case.id,
        evidence_version=ev_v,
        diagnosis_version=diag_v,
        app_path=str(FIXTURE_ROOT),
        unified_diff=build_fixture_fix_diff(),
    )
    assert payload.patch.unified_diff
    assert payload.patch.evidence_version == ev_v
    assert payload.patch.diagnosis_version == diag_v
    assert payload.sandbox is None

    after = orch.run_patch_sandbox(
        workspace_id=workspace.id,
        case_id=case.id,
        patch_version=payload.patch.version,
        network_policy_available=True,
    )
    assert after.sandbox is not None
    assert after.sandbox.passed is True
    assert after.sandbox.secrets_scrubbed is True
    assert after.sandbox.ready_for_release is True
    assert after.sandbox.network_isolated is True
    assert orch.write_guard.call_count == writes_before  # no Liara write

    # Diff + sandbox persisted on case
    store = orch._case_store(case)  # noqa: SLF001
    assert store["latest_patch_version"] == payload.patch.version
    assert store["latest_sandbox"]["passed"] is True


def test_red_tests_block_release_no_auto_release(
    orch: OrchestratorService, workspace: Workspace
) -> None:
    case, ev_v, diag_v = _seed_evidence_diagnosis(orch, workspace)
    writes_before = orch.write_guard.call_count

    payload = orch.create_patch(
        workspace_id=workspace.id,
        case_id=case.id,
        evidence_version=ev_v,
        diagnosis_version=diag_v,
        app_path=str(FIXTURE_ROOT),
        unified_diff=RED_DIFF,
        rationale="noop diff — should stay red",
    )
    after = orch.run_patch_sandbox(
        workspace_id=workspace.id,
        case_id=case.id,
        patch_version=payload.patch.version,
        network_policy_available=True,
    )
    assert after.sandbox is not None
    assert after.sandbox.passed is False
    assert after.sandbox.ready_for_release is False

    # Patch record can still be approved (git/record ≠ release).
    _plan, record_approval, recorded = orch.approve_patch_record(
        workspace_id=workspace.id,
        case_id=case.id,
        patch_version=payload.patch.version,
    )
    assert record_approval.scope is not None
    assert record_approval.scope.get("kind") == APPROVAL_KIND_PATCH_RECORD
    assert recorded.patch_record_approved is True
    assert recorded.can_approve_release is False

    with pytest.raises(OrchestratorError) as exc_info:
        orch.approve_release(
            workspace_id=workspace.id,
            case_id=case.id,
            patch_version=payload.patch.version,
            project_name="demo",
            archive_path="/tmp/demo.tar.gz",
        )
    assert exc_info.value.code in (
        "release_blocked_sandbox",
        "release_blocked_red_tests",
    )
    assert orch.write_guard.call_count == writes_before


def test_network_policy_unavailable_blocks_release_even_if_green(
    orch: OrchestratorService, workspace: Workspace
) -> None:
    case, ev_v, diag_v = _seed_evidence_diagnosis(orch, workspace)

    payload = orch.create_patch(
        workspace_id=workspace.id,
        case_id=case.id,
        evidence_version=ev_v,
        diagnosis_version=diag_v,
        app_path=str(FIXTURE_ROOT),
    )
    after = orch.run_patch_sandbox(
        workspace_id=workspace.id,
        case_id=case.id,
        patch_version=payload.patch.version,
        network_policy_available=False,
    )
    assert after.sandbox is not None
    assert after.sandbox.passed is True  # tests can still run
    assert after.sandbox.network_isolated is False
    assert after.sandbox.ready_for_release is False
    assert after.sandbox.limitation
    assert "Network isolation" in (after.sandbox.limitation or "")

    orch.approve_patch_record(
        workspace_id=workspace.id,
        case_id=case.id,
        patch_version=payload.patch.version,
    )
    with pytest.raises(OrchestratorError) as exc_info:
        orch.approve_release(
            workspace_id=workspace.id,
            case_id=case.id,
            patch_version=payload.patch.version,
            project_name="demo",
            archive_path="/tmp/demo.tar.gz",
        )
    assert exc_info.value.code == "release_blocked_sandbox"


def test_approve_patch_record_distinct_from_approve_release(
    orch: OrchestratorService, workspace: Workspace
) -> None:
    case, ev_v, diag_v = _seed_evidence_diagnosis(orch, workspace)

    payload = orch.create_patch(
        workspace_id=workspace.id,
        case_id=case.id,
        evidence_version=ev_v,
        diagnosis_version=diag_v,
        app_path=str(FIXTURE_ROOT),
    )
    orch.run_patch_sandbox(
        workspace_id=workspace.id,
        case_id=case.id,
        patch_version=payload.patch.version,
        network_policy_available=True,
    )
    _p1, a1, mid = orch.approve_patch_record(
        workspace_id=workspace.id,
        case_id=case.id,
        patch_version=payload.patch.version,
    )
    assert a1.scope and a1.scope.get("kind") == APPROVAL_KIND_PATCH_RECORD
    assert mid.release_approved is False

    _p2, a2, final = orch.approve_release(
        workspace_id=workspace.id,
        case_id=case.id,
        patch_version=payload.patch.version,
        project_name="demo-app",
        archive_path="/tmp/demo-app.tar.gz",
        port=3000,
    )
    assert a2.scope and a2.scope.get("kind") == APPROVAL_KIND_RELEASE
    assert a1.id != a2.id
    assert final.patch_record_approved is True
    assert final.release_approved is True
    # Distinct kinds — record approval must never equal release.
    assert a1.scope.get("kind") != a2.scope.get("kind")


def test_sandbox_run_promoted_tested(
    orch: OrchestratorService, workspace: Workspace, db_session: Session
) -> None:
    registry = CapabilityRegistry(db_session)
    registry.seed()
    assert registry.get("sandbox_run").status == "documented"

    case, ev_v, diag_v = _seed_evidence_diagnosis(orch, workspace)
    payload = orch.create_patch(
        workspace_id=workspace.id,
        case_id=case.id,
        evidence_version=ev_v,
        diagnosis_version=diag_v,
        app_path=str(FIXTURE_ROOT),
    )
    orch.run_patch_sandbox(
        workspace_id=workspace.id,
        case_id=case.id,
        patch_version=payload.patch.version,
        network_policy_available=False,
    )
    assert registry.get("sandbox_run").status == "tested"


def test_sandbox_does_not_read_secret_env_in_child(
    orch: OrchestratorService, workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pollute process env; sandbox child must still scrub (L-AC46)."""
    monkeypatch.setenv("SECRETS_MASTER_KEY", "master-should-not-reach-child")
    monkeypatch.setenv("LIARA_API_TOKEN", "prod-token-should-not-reach-child")

    case, ev_v, diag_v = _seed_evidence_diagnosis(orch, workspace)
    payload = orch.create_patch(
        workspace_id=workspace.id,
        case_id=case.id,
        evidence_version=ev_v,
        diagnosis_version=diag_v,
        app_path=str(FIXTURE_ROOT),
    )
    after = orch.run_patch_sandbox(
        workspace_id=workspace.id,
        case_id=case.id,
        patch_version=payload.patch.version,
        network_policy_available=True,
    )
    assert after.sandbox is not None
    assert after.sandbox.secrets_scrubbed is True
    assert after.sandbox.passed is True
    # Outcome must not echo secret values.
    blob = (after.sandbox.stdout_excerpt or "") + (after.sandbox.stderr_excerpt or "")
    assert "master-should-not-reach-child" not in blob
    assert "prod-token-should-not-reach-child" not in blob

"""Schema-validated plan / approval / operation contracts.

Model output must validate against these before any executor side effect.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class PlanStep(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    action: str = Field(min_length=1, max_length=256)
    tool_id: str | None = Field(default=None, max_length=128)
    effects: list[str] = Field(default_factory=list)
    cost_known: bool = False
    cost_estimate: str | None = None
    # Deploy params (name, planID, platform, port, archive_path, …) — never secrets.
    params: dict[str, Any] = Field(default_factory=dict)


class PlanVersion(BaseModel):
    """Consequential plan draft — LLM may propose; executor never runs raw text."""

    version: int = Field(default=1, ge=1)
    steps: list[PlanStep] = Field(min_length=1)
    effects: list[str] = Field(default_factory=list)
    cost_known: bool = False
    cost_summary: str | None = None
    summary: str | None = None
    target_platform: str | None = None  # nodejs | next

    @field_validator("steps")
    @classmethod
    def steps_must_be_non_empty(cls, value: list[PlanStep]) -> list[PlanStep]:
        if not value:
            raise ValueError("plan must include at least one step")
        return value


class ApprovalPayload(BaseModel):
    plan_hash: str = Field(min_length=8, max_length=128)
    expires_at: datetime
    scope: dict[str, Any] = Field(default_factory=dict)
    status: Literal["approved", "rejected", "pending"] = "approved"


class OperationPayload(BaseModel):
    id: uuid.UUID
    state: str
    fingerprints: list[str] = Field(default_factory=list)
    client_request_id: str | None = None
    plan_id: uuid.UUID | None = None
    case_id: uuid.UUID | None = None
    checkpoint: dict[str, Any] | None = None


class FindingPayload(BaseModel):
    code: str
    message: str
    evidence_paths: list[str] = Field(default_factory=list)
    severity: str = "error"


class ReadinessAssessment(BaseModel):
    ready: bool
    open_needs: list[str] = Field(default_factory=list)
    notes: str | None = None
    platform: str | None = None
    package_name: str | None = None
    findings: list[FindingPayload] = Field(default_factory=list)
    detected_port: int | None = None
    start_script: str | None = None
    # DevOps-style prerequisites (DB/Redis/disk) — optional for older clients.
    required_dependencies: list[str] = Field(default_factory=list)
    dependency_summary: str | None = None
    existing_databases: list[str] = Field(default_factory=list)


# --- Phase 3: evidence + diagnosis (no invented confidence %) -----------------


class EvidenceFact(BaseModel):
    """Observed fact with provenance — not a causal claim."""

    id: str = Field(min_length=1, max_length=64)
    source: Literal["status", "logs", "events", "metrics_cpu", "metrics_memory", "other"]
    summary: str = Field(min_length=1, max_length=1024)
    observed_at: str | None = None
    stale: bool = False
    raw_ref: str | None = None  # opaque pointer; never secret values


class EvidenceGap(BaseModel):
    """Missing or incomplete data — must not be treated as empty success."""

    source: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=512)
    impact: str = Field(min_length=1, max_length=512)


class EvidencePack(BaseModel):
    """Versioned evidence bundle from collect_evidence (L-R07)."""

    version: str = Field(min_length=8, max_length=128)
    project_name: str = Field(min_length=1, max_length=128)
    symptom: str | None = None
    window_note: str | None = None
    collected_at: str
    facts: list[EvidenceFact] = Field(default_factory=list)
    gaps: list[EvidenceGap] = Field(default_factory=list)
    sanitized_log_excerpts: list[str] = Field(default_factory=list)
    injection_stripped_count: int = 0
    complete: bool = False  # False when gaps prevent confident diagnosis


class Hypothesis(BaseModel):
    """Ranked causal guess — ordinal rank only, never confidence %."""

    id: str = Field(min_length=1, max_length=64)
    rank: int = Field(ge=1, le=20)
    statement: str = Field(min_length=1, max_length=1024)
    supporting_fact_ids: list[str] = Field(default_factory=list)
    contradicting_fact_ids: list[str] = Field(default_factory=list)
    # Explicitly forbid invented percentages in API surface.
    # confidence_percent is intentionally absent.


class Diagnosis(BaseModel):
    """Schema-validated diagnosis — facts vs hypotheses vs gaps (L-AC13/14)."""

    version: str = Field(min_length=8, max_length=128)
    evidence_version: str = Field(min_length=8, max_length=128)
    created_at: str
    facts: list[EvidenceFact] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    data_gaps: list[EvidenceGap] = Field(default_factory=list)
    summary: str | None = None
    next_read_or_question: str | None = None
    # When evidence incomplete: do not invent a root cause.
    insufficient_evidence: bool = False


class FixOption(BaseModel):
    """Direct-fix candidate — only allowlisted tools; still needs approval."""

    id: str = Field(min_length=1, max_length=64)
    tool_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    rationale: str = Field(min_length=1, max_length=1024)
    enabled: bool = False
    disabled_reason: str | None = None
    verification_method: str = Field(min_length=1, max_length=256)
    params: dict[str, Any] = Field(default_factory=dict)


class FixOptionsPayload(BaseModel):
    diagnosis_version: str
    evidence_version: str
    options: list[FixOption] = Field(default_factory=list)
    open_needs: list[str] = Field(default_factory=list)


class FixVerification(BaseModel):
    """Before/after check using the same method (L-AC17)."""

    method: str
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    effective: bool | None = None  # None = insufficient after data
    open_need: str | None = None
    autonomous_next_write: bool = False  # always False — hard ban (L-AC17)


# --- Phase 4: dependencies (DB / Redis / disk) --------------------------------


class DependencyFindingPayload(BaseModel):
    kind: str
    code: str
    message: str
    evidence_paths: list[str] = Field(default_factory=list)
    required: bool = True
    severity: str = "error"


class DependencyDiscoveryPayload(BaseModel):
    findings: list[DependencyFindingPayload] = Field(default_factory=list)
    required_kinds: list[str] = Field(default_factory=list)
    notes: str | None = None
    app_root: str | None = None
    has_required: bool = False


class DependencyPlanPayload(BaseModel):
    """GenUI ``dependency_plan`` — create flags match registry honesty."""

    version: str
    discovery: DependencyDiscoveryPayload
    proposed_creates: list[dict[str, Any]] = Field(default_factory=list)
    create_database_enabled: bool = False
    create_disk_enabled: bool = False
    open_needs: list[str] = Field(default_factory=list)
    handoff: dict[str, Any] | None = None
    pending_resources: list[dict[str, Any]] = Field(default_factory=list)
    can_claim_complete_success: bool = False
    summary: str | None = None


# --- Phase 5: code patch + sandbox (separate record vs release approvals) -----


class PatchProposal(BaseModel):
    """Limited code patch — unified diff + rationale tied to evidence/diagnosis."""

    version: str = Field(min_length=8, max_length=128)
    evidence_version: str = Field(min_length=8, max_length=128)
    diagnosis_version: str = Field(min_length=8, max_length=128)
    hypothesis_id: str | None = Field(default=None, max_length=64)
    created_at: str
    rationale: str = Field(min_length=1, max_length=2048)
    unified_diff: str = Field(min_length=1, max_length=200_000)
    files_changed: list[str] = Field(default_factory=list)
    content_hash: str = Field(min_length=8, max_length=128)
    base_path: str | None = None  # source fixture/project root (not live prod)
    base_commit: str | None = None


class PatchSandboxResult(BaseModel):
    """Sandbox build/test outcome — red tests never imply ready_for_release."""

    patch_applied: bool = False
    files_touched: list[str] = Field(default_factory=list)
    command: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    passed: bool = False
    stdout_excerpt: str = ""
    stderr_excerpt: str = ""
    network_isolated: bool = False
    secrets_scrubbed: bool = False
    ready_for_release: bool = False  # False on red / non-isolated (L-AC46)
    limitation: str | None = None
    work_dir: str | None = None
    duration_ms: int = 0


class PatchDiffPayload(BaseModel):
    """GenUI ``patch_diff`` — preview + sandbox honesty + approval kinds."""

    patch: PatchProposal
    sandbox: PatchSandboxResult | None = None
    patch_record_approved: bool = False
    release_approved: bool = False
    can_approve_release: bool = False
    open_needs: list[str] = Field(default_factory=list)
    summary: str | None = None


# --- Phase 6: monitor / incident / recovery -----------------------------------


class MonitorStatusPayload(BaseModel):
    """GenUI ``monitor_status`` — enable ≠ write permission; stale ≠ live green."""

    monitor_id: str
    target: str
    enabled: bool
    interval_seconds: int = 60
    last_status: str = "never"
    last_checked_at: str | None = None
    last_data_at: str | None = None
    consecutive_misses: int = 0
    stale: bool = False
    healthy_live: bool = False
    grants_write_permission: bool = False
    notification_allowed: bool = True
    criteria: dict[str, Any] = Field(default_factory=dict)


class IncidentCardPayload(BaseModel):
    """GenUI ``incident_card`` — alert ≠ restart/write authorization."""

    incident_id: str
    monitor_id: str | None = None
    case_id: str | None = None
    status: str
    title: str
    alert_count: int = 1
    dedupe_key: str
    write_authorized: bool = False
    opened_at: str | None = None
    resolved_at: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    resolve_evidence: str | None = None


class RecoveryPlanPayload(BaseModel):
    """GenUI ``recovery_plan`` — requires fresh approval; monitor/incident never authorize."""

    baseline_id: str
    project_name: str
    action: Literal["restart", "republish"]
    requires_fresh_approval: bool = True
    monitor_enable_authorizes: bool = False
    incident_alert_authorizes: bool = False
    plan: dict[str, Any] = Field(default_factory=dict)
    snapshot_keys: list[str] = Field(default_factory=list)
    summary: str | None = None
    open_needs: list[str] = Field(default_factory=list)

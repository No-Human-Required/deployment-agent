"""Orchestrator service — BFF command implementations (propose ≠ execute).

Hard rules:
- Invalid PlanVersion JSON → zero WriteGuard calls
- Execute requires a non-expired approved Approval whose plan_hash matches
- Secrets never enter LLM prompts (labels/refs only)
- Liara writes only via WriteGuard allowlist after approval (slice 05)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.node_next import assess_node_next
from app.config import Settings, get_settings
from app.models.audit import AuditEvent
from app.models.case import Case
from app.models.stubs import Approval, Operation, Plan
from app.schemas.orchestration import (
    ApprovalPayload,
    DependencyPlanPayload,
    Diagnosis,
    EvidencePack,
    FindingPayload,
    FixOptionsPayload,
    FixVerification,
    IncidentCardPayload,
    MonitorStatusPayload,
    OperationPayload,
    PatchDiffPayload,
    PatchProposal,
    PatchSandboxResult,
    PlanVersion,
    ReadinessAssessment,
    RecoveryPlanPayload,
)
from app.services.dependencies import (
    DEP_WRITE_TOOLS,
    build_dependency_plan_view,
    build_deps_plan_body,
    discover_dependencies,
    execute_dependency_steps,
)
from app.services.deploy import (
    OP_STATE_DEPLOYED,
    OP_STATE_UNKNOWN,
    OP_STATE_VERIFIED,
    OP_STATE_VERIFY_FAILED,
    build_node_next_plan,
    execute_deploy_steps,
    live_writes_allowed,
    promote_deploy_tools_tested,
    verify_deploy,
)
from app.services.liara_client import LiaraClient
from app.services.llm import LlmService
from app.services.ops import (
    ENV_OPEN_NEED,
    OPS_WRITE_TOOLS,
    build_domain_ssl_plan,
    build_env_update_plan,
    build_restart_plan,
    build_resize_plan,
    ensure_update_envs_disabled,
    execute_ops_steps,
    promote_ops_tools_tested,
)
from app.services.patch import (
    APPROVAL_KIND_PATCH_RECORD,
    APPROVAL_KIND_RELEASE,
    approval_kind_of,
    build_patch_record_plan,
    build_release_plan_from_patch,
    create_patch_proposal,
    patch_record_scope,
    release_scope,
    run_sandbox,
)
from app.services.registry import CapabilityRegistry
from app.services.secrets import SecretService
from app.services.settings import SettingsService
from app.services.troubleshoot import (
    build_fix_options,
    collect_evidence_from_client,
    diagnose_from_evidence,
    fix_option_to_ops_cfg,
    refuse_autonomous_next_write,
    verify_fix_same_method,
)
from app.services.maintain import (
    MaintainService,
    ensure_documented_adapters,
    incident_to_card,
    monitor_to_status,
)
from app.services.roles import RoleDeniedError, RolesService
from app.services.write_guard import ALLOWLISTED_WRITE_TOOLS, WriteGuard

DEFAULT_APPROVAL_TTL = timedelta(hours=1)
OP_STATE_PLANNED = "planned"
OP_STATE_AWAITING_PROVIDER = "awaiting_provider"
OP_STATE_VERIFIED_STUB = "verified_stub"
OP_STATE_BLOCKED = "blocked"


class OrchestratorError(Exception):
    """Base orchestrator failure (maps to 4xx in API)."""

    def __init__(self, message: str, *, code: str = "orchestrator_error") -> None:
        super().__init__(message)
        self.code = code


class SchemaValidationError(OrchestratorError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="schema_invalid")


class ApprovalRequiredError(OrchestratorError):
    def __init__(self, message: str = "valid approval required before execute") -> None:
        super().__init__(message, code="approval_required")


class ApprovalExpiredError(OrchestratorError):
    def __init__(self, message: str = "approval has expired") -> None:
        super().__init__(message, code="approval_expired")


class PlanHashMismatchError(OrchestratorError):
    def __init__(self, message: str = "approval plan_hash does not match plan") -> None:
        super().__init__(message, code="plan_hash_mismatch")


class RoleForbiddenError(OrchestratorError):
    def __init__(self, message: str = "viewer cannot execute writes") -> None:
        super().__init__(message, code="role_denied")


def plan_content_hash(plan: PlanVersion) -> str:
    payload = plan.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrchestratorService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        *,
        write_guard: WriteGuard | None = None,
        llm: LlmService | None = None,
        chat_model: Any | None = None,
        liara_client: LiaraClient | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._liara_client = liara_client
        self.write_guard = write_guard or WriteGuard(
            liara_client=liara_client if self._writes_enabled() else None
        )
        self._llm = llm or LlmService(session, self._settings)
        # Injected FakeListChatModel (or similar) for tests; never used for writes.
        self._chat_model = chat_model

    def _writes_enabled(self) -> bool:
        """HTTP writes only when explicit live gate is on, or a client was injected (tests)."""
        if self._liara_client is not None:
            return True
        return bool(self._settings.liara_allow_live_writes) and live_writes_allowed()

    def resolve_liara_client(self, workspace_id: uuid.UUID) -> LiaraClient | None:
        if self._liara_client is not None:
            return self._liara_client
        if not self._writes_enabled():
            return None
        try:
            token, base, team = SettingsService(
                self._session, self._settings
            ).resolve_liara_credentials(workspace_id)
        except LookupError:
            return None
        return LiaraClient(
            token,
            base_url=base,
            team_id=team,
            timeout=self._settings.liara_http_timeout_seconds,
        )

    def resolve_liara_client_for_read(
        self, workspace_id: uuid.UUID
    ) -> LiaraClient | None:
        """Read path — credentials even when live writes are off (evidence collect)."""
        if self._liara_client is not None:
            return self._liara_client
        try:
            token, base, team = SettingsService(
                self._session, self._settings
            ).resolve_liara_credentials(workspace_id)
        except LookupError:
            return None
        return LiaraClient(
            token,
            base_url=base,
            team_id=team,
            timeout=self._settings.liara_http_timeout_seconds,
        )

    # --- cases -----------------------------------------------------------------

    def ensure_case(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID | None = None,
        goal: str | None = None,
    ) -> Case:
        if case_id is not None:
            case = self._session.get(Case, case_id)
            if case is None or case.workspace_id != workspace_id:
                raise OrchestratorError("case not found", code="case_not_found")
            return case
        if not goal:
            raise OrchestratorError(
                "goal required when creating a case", code="goal_required"
            )
        case = Case(
            workspace_id=workspace_id,
            goal=goal,
            status="open",
        )
        self._session.add(case)
        self._session.flush()
        return case

    # --- assess_readiness ------------------------------------------------------

    def assess_readiness(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        app_path: str | None = None,
    ) -> ReadinessAssessment:
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        open_needs: list[str] = []
        findings: list[FindingPayload] = []
        platform: str | None = None
        detected_port: int | None = None
        start_script: str | None = None

        # Labels only — never resolve secret values into assessment text.
        llm_cfg = self._llm.resolve_config(workspace_id)
        if llm_cfg is None:
            open_needs.append("llm_stub_mode")

        path = app_path
        if not path and isinstance(case.constraints, dict):
            raw = case.constraints.get("app_path")
            if isinstance(raw, str) and raw.strip():
                path = raw.strip()

        notes_parts = [f"case={case.id}"]
        ready = True
        if path:
            result = assess_node_next(path)
            platform = result.platform
            detected_port = result.detected_port
            start_script = result.start_script
            findings = [
                FindingPayload(
                    code=f.code,
                    message=f.message,
                    evidence_paths=list(f.evidence_paths),
                    severity=f.severity,
                )
                for f in result.findings
            ]
            for f in result.findings:
                if f.severity == "error":
                    open_needs.append(f.code)
            ready = result.ready
            notes_parts.append(result.notes or f"app_path={path}")
        else:
            notes_parts.append("no app_path — LLM/orchestration readiness only")

        assessment = ReadinessAssessment(
            ready=ready and (llm_cfg is not None or "llm_stub_mode" in open_needs),
            open_needs=open_needs,
            notes="; ".join(notes_parts),
            platform=platform,
            findings=findings,
            detected_port=detected_port,
            start_script=start_script,
        )
        # Stub orchestration remains usable without Aval; Node findings still surface.
        if path is None:
            assessment = assessment.model_copy(
                update={
                    "ready": True,
                    "notes": (
                        f"پرونده={case.id}؛ "
                        f"{'مدل زبانی آماده است' if llm_cfg else 'مدل زبانی تنظیم نشده — حالت ساده'}"
                    ),
                }
            )

        self._audit(
            workspace_id,
            case.id,
            "assess_readiness",
            assessment.model_dump(mode="json"),
        )
        return assessment

    # --- create_plan -----------------------------------------------------------

    def create_plan(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        plan_draft: dict[str, Any] | PlanVersion | None = None,
        use_llm: bool = False,
        deploy: dict[str, Any] | None = None,
        ops: dict[str, Any] | None = None,
        deps: dict[str, Any] | None = None,
    ) -> tuple[Plan, PlanVersion]:
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)

        raw: dict[str, Any]
        if plan_draft is None:
            raw = self._draft_plan_payload(
                case, use_llm=use_llm, deploy=deploy, ops=ops, deps=deps
            )
        elif isinstance(plan_draft, PlanVersion):
            raw = plan_draft.model_dump(mode="json")
        else:
            raw = plan_draft

        try:
            validated = PlanVersion.model_validate(raw)
        except ValidationError as exc:
            # Fail closed: no Plan row, no write side effects.
            raise SchemaValidationError(
                f"plan schema invalid: {exc.errors()[0]['msg']}"
            ) from exc

        content_hash = plan_content_hash(validated)
        version = self._next_plan_version(case.id)
        row = Plan(
            workspace_id=workspace_id,
            case_id=case.id,
            version=version,
            content_hash=content_hash,
            body=validated.model_dump(mode="json"),
        )
        self._session.add(row)
        self._session.flush()
        self._audit(
            workspace_id,
            case.id,
            "create_plan",
            {"plan_id": str(row.id), "content_hash": content_hash},
        )
        return row, validated

    def _draft_plan_payload(
        self,
        case: Case,
        *,
        use_llm: bool,
        deploy: dict[str, Any] | None = None,
        ops: dict[str, Any] | None = None,
        deps: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Node/Next first-publish, phase-2 ops, phase-4 deps, or stub/LLM."""
        constraints = case.constraints if isinstance(case.constraints, dict) else {}
        ops_cfg = dict(ops or {})
        if not ops_cfg and constraints.get("ops"):
            nested_ops = constraints["ops"]
            if isinstance(nested_ops, dict):
                ops_cfg = dict(nested_ops)

        ops_plan = self._draft_ops_plan(ops_cfg)
        if ops_plan is not None:
            return ops_plan

        deps_cfg = dict(deps or {})
        if not deps_cfg and constraints.get("deps"):
            nested_deps = constraints["deps"]
            if isinstance(nested_deps, dict):
                deps_cfg = dict(nested_deps)
        deps_plan = self._draft_deps_plan(case, deps_cfg)
        if deps_plan is not None:
            return deps_plan

        deploy_cfg = dict(deploy or {})
        if not deploy_cfg and constraints.get("deploy"):
            nested = constraints["deploy"]
            if isinstance(nested, dict):
                deploy_cfg = dict(nested)

        if deploy_cfg.get("archive_path") and deploy_cfg.get("project_name"):
            platform = str(deploy_cfg.get("platform") or "node")
            return build_node_next_plan(
                project_name=str(deploy_cfg["project_name"]),
                plan_id=str(deploy_cfg.get("plan_id") or deploy_cfg.get("planID") or "free"),
                platform=platform,
                port=int(deploy_cfg.get("port") or 3000),
                archive_path=str(deploy_cfg["archive_path"]),
                summary=f"اولین انتشار برای: {case.goal[:200]}",
            )

        # Infer Node/Next from app_path readiness when present.
        app_path = deploy_cfg.get("app_path") or constraints.get("app_path")
        if isinstance(app_path, str) and app_path.strip():
            readiness = assess_node_next(app_path)
            name = (
                str(deploy_cfg.get("project_name"))
                if deploy_cfg.get("project_name")
                else f"demo-{uuid.uuid4().hex[:8]}"
            )
            archive = deploy_cfg.get("archive_path") or str(
                Path(app_path) / "source.tar.gz"
            )
            platform = "next" if readiness.platform == "next" else "node"
            return build_node_next_plan(
                project_name=name,
                plan_id=str(deploy_cfg.get("plan_id") or "free"),
                platform=platform,
                port=int(deploy_cfg.get("port") or readiness.detected_port or 3000),
                archive_path=str(archive),
                summary=f"طرح استقرار برای: {case.goal[:200]}",
            )

        stub = {
            "version": 1,
            "steps": [
                {
                    "id": "step-1",
                    "action": "prepare_deploy_stub",
                    "tool_id": "create_project",
                    "effects": ["would_create_project"],
                    "cost_known": False,
                    "cost_estimate": None,
                    "params": {},
                }
            ],
            "effects": ["would_create_project"],
            "cost_known": False,
            "cost_summary": "unknown",
            "summary": (
                f"طرح پیشنهادی برای هدف شما: {case.goal[:200]}. "
                "جزئیات استقرار و رمزها جداگانه گرفته می‌شود."
            ),
        }
        if not use_llm:
            return stub

        model = self._chat_model or self._llm.build_chat_model(case.workspace_id)
        if model is None:
            return stub

        # Prompt uses case goal text only — never secret values.
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(
                content=(
                    "فقط JSON مطابق PlanVersion برگردان: version, steps "
                    "[{id,action,tool_id,effects,cost_known,cost_estimate,params}], "
                    "effects, cost_known, cost_summary, summary, target_platform. "
                    "tool_idهای مجاز: create_project, sources, releases. "
                    "فیلد summary و توضیحات را به فارسی ساده و روان بنویس؛ "
                    "از واژه‌های تخصصی انگلیسی مثل orchestrator پرهیز کن. "
                    "رمز یا توکن ننویس."
                )
            ),
            HumanMessage(
                content=(
                    f"یک طرح استقرار به فارسی بنویس. شناسه پرونده={case.id} "
                    f"هدف={case.goal[:500]}. "
                    "فقط برچسب tool_id؛ رمز اختراع نکن."
                )
            ),
        ]
        try:
            response = model.invoke(messages)
            content = getattr(response, "content", response)
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            text = str(content).strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:].strip()
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                return stub
            return self._normalize_llm_plan_dict(parsed, fallback=stub)
        except (json.JSONDecodeError, TypeError, ValueError):
            # Fail soft to stub — bad LLM shape must not break greeting/chat paths.
            return stub

    def _next_plan_version(self, case_id: uuid.UUID) -> int:
        latest = self._session.scalar(
            select(Plan.version)
            .where(Plan.case_id == case_id)
            .order_by(Plan.version.desc())
            .limit(1)
        )
        return int(latest or 0) + 1

    @staticmethod
    def _normalize_llm_plan_dict(
        raw: dict[str, Any], *, fallback: dict[str, Any]
    ) -> dict[str, Any]:
        """Coerce common LLM shape mistakes so PlanVersion can validate."""
        out = dict(fallback)
        out.update({k: v for k, v in raw.items() if v is not None})

        steps = out.get("steps")
        if isinstance(steps, dict):
            steps = [steps]
        elif isinstance(steps, str):
            steps = [
                {
                    "id": "llm-1",
                    "action": steps.strip() or "review_goal",
                    "tool_id": None,
                    "effects": [],
                    "params": {},
                }
            ]
        elif not isinstance(steps, list):
            steps = list(fallback.get("steps") or [])
        if not steps:
            steps = list(fallback.get("steps") or [])
        # Ensure each step has list-typed effects.
        normalized_steps: list[Any] = []
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            item = dict(step)
            step_effects = item.get("effects")
            if isinstance(step_effects, str):
                item["effects"] = [step_effects] if step_effects.strip() else []
            elif not isinstance(step_effects, list):
                item["effects"] = []
            if not item.get("id"):
                item["id"] = f"llm-{index + 1}"
            if not item.get("action"):
                item["action"] = "review_goal"
            if not isinstance(item.get("params"), dict):
                item["params"] = {}
            normalized_steps.append(item)
        out["steps"] = normalized_steps or list(fallback.get("steps") or [])

        effects = out.get("effects")
        if isinstance(effects, str):
            effects = [effects] if effects.strip() else []
        elif not isinstance(effects, list):
            effects = list(fallback.get("effects") or [])
        out["effects"] = effects

        if "version" in out and not isinstance(out["version"], int):
            try:
                out["version"] = int(out["version"])
            except (TypeError, ValueError):
                out["version"] = 1

        return out

    def _draft_ops_plan(self, ops_cfg: dict[str, Any]) -> dict[str, Any] | None:
        """Build phase-2 plan from ops intent (restart/resize/domain/env)."""
        if not ops_cfg:
            return None
        kind = str(ops_cfg.get("kind") or ops_cfg.get("action") or "").lower()
        project = str(ops_cfg.get("project_name") or ops_cfg.get("project") or "")
        if kind in ("restart", "restart_project") and project:
            return build_restart_plan(
                project_name=project, reason=ops_cfg.get("reason")
            )
        if kind in ("resize", "change_plan") and project:
            plan_id = str(ops_cfg.get("plan_id") or ops_cfg.get("planID") or "")
            if plan_id:
                return build_resize_plan(project_name=project, plan_id=plan_id)
        if kind in ("domain", "domain_ssl", "ssl") and project:
            domain = str(ops_cfg.get("domain_name") or ops_cfg.get("domain") or "")
            if domain:
                return build_domain_ssl_plan(
                    project_name=project,
                    domain_name=domain,
                    provision_ssl=bool(ops_cfg.get("provision_ssl", True)),
                )
        if kind in ("env", "update_envs", "env_update") and project:
            variables = ops_cfg.get("variables") or []
            if isinstance(variables, list) and variables:
                return build_env_update_plan(
                    project_name=project,
                    variables=[
                        {"key": str(v["key"]), "value": str(v.get("value", ""))}
                        for v in variables
                        if isinstance(v, dict) and v.get("key")
                    ],
                )
        return None

    def _draft_deps_plan(
        self, case: Case, deps_cfg: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Build phase-4 plan from discover result or explicit deps intent."""
        if not deps_cfg:
            return None
        app_path = deps_cfg.get("app_path")
        constraints = case.constraints if isinstance(case.constraints, dict) else {}
        discovery_raw = deps_cfg.get("discovery") or constraints.get("dependency_discovery")
        if app_path and not discovery_raw:
            discovery = discover_dependencies(str(app_path))
            discovery_raw = discovery.to_dict()
        if not discovery_raw and not deps_cfg.get("force"):
            return None

        from app.services.dependencies import DependencyDiscovery, DependencyFinding

        if isinstance(discovery_raw, dict):
            findings = tuple(
                DependencyFinding(
                    kind=str(f.get("kind") or "unknown"),
                    code=str(f.get("code") or "unknown"),
                    message=str(f.get("message") or ""),
                    evidence_paths=tuple(f.get("evidence_paths") or ()),
                    required=bool(f.get("required", True)),
                    severity=str(f.get("severity") or "error"),
                )
                for f in (discovery_raw.get("findings") or [])
                if isinstance(f, dict)
            )
            discovery = DependencyDiscovery(
                findings=findings,
                required_kinds=tuple(discovery_raw.get("required_kinds") or ()),
                notes=discovery_raw.get("notes"),
                app_root=discovery_raw.get("app_root"),
            )
        else:
            return None

        registry = CapabilityRegistry(self._session)
        pending = list(constraints.get("pending_resources") or [])
        view = build_dependency_plan_view(
            discovery,
            registry=registry,
            pending_resources=pending,
            project_name=str(deps_cfg.get("project_name") or "app"),
            hostname_prefix=str(deps_cfg.get("hostname_prefix") or "dep"),
            plan_id=str(deps_cfg.get("plan_id") or deps_cfg.get("planID") or "small"),
        )
        # Persist plan view on case for GenUI.
        constraints = dict(constraints)
        constraints["dependency_plan"] = view.to_dict()
        constraints["dependency_discovery"] = discovery.to_dict()
        case.constraints = constraints
        self._session.flush()

        body = build_deps_plan_body(view, only_enabled=False)
        return body

    def discover_dependencies(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        app_path: str,
        project_name: str | None = None,
    ) -> DependencyPlanPayload:
        """File-backed discovery + GenUI dependency_plan (create gated by registry)."""
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        discovery = discover_dependencies(app_path)
        registry = CapabilityRegistry(self._session)
        constraints = case.constraints if isinstance(case.constraints, dict) else {}
        pending = list(constraints.get("pending_resources") or [])
        view = build_dependency_plan_view(
            discovery,
            registry=registry,
            pending_resources=pending,
            project_name=project_name or "app",
        )
        constraints = dict(constraints)
        constraints["dependency_discovery"] = discovery.to_dict()
        constraints["dependency_plan"] = view.to_dict()
        # Required deps block "complete success" on the case.
        if discovery.required_kinds and not view.can_claim_complete_success:
            open_needs = list(constraints.get("open_needs") or [])
            for need in view.open_needs:
                if need not in open_needs:
                    open_needs.append(need)
            constraints["open_needs"] = open_needs
        case.constraints = constraints
        self._session.flush()
        self._audit(
            workspace_id,
            case.id,
            "discover_dependencies",
            {
                "required_kinds": list(discovery.required_kinds),
                "can_claim_complete_success": view.can_claim_complete_success,
                "open_needs": view.open_needs,
            },
        )
        return DependencyPlanPayload.model_validate(view.to_dict())

    # --- approve_plan ----------------------------------------------------------

    def approve_plan(
        self,
        *,
        workspace_id: uuid.UUID,
        plan_id: uuid.UUID,
        scope: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
        status: str = "approved",
    ) -> Approval:
        plan = self._session.get(Plan, plan_id)
        if plan is None or plan.workspace_id != workspace_id:
            raise OrchestratorError("plan not found", code="plan_not_found")
        if not plan.content_hash:
            raise OrchestratorError("plan missing content_hash", code="plan_invalid")

        expiry = expires_at or (_utcnow() + DEFAULT_APPROVAL_TTL)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        payload = ApprovalPayload(
            plan_hash=plan.content_hash,
            expires_at=expiry,
            scope=scope or {"actions": ["execute_deploy"]},
            status=status if status in ("approved", "rejected", "pending") else "approved",  # type: ignore[arg-type]
        )

        row = Approval(
            workspace_id=workspace_id,
            plan_id=plan.id,
            status=payload.status,
            plan_hash=payload.plan_hash,
            scope=payload.scope,
            expires_at=payload.expires_at,
        )
        self._session.add(row)
        self._session.flush()
        self._audit(
            workspace_id,
            plan.case_id,
            "approve_plan",
            {
                "approval_id": str(row.id),
                "plan_id": str(plan.id),
                "plan_hash": row.plan_hash,
                "status": row.status,
            },
        )
        return row

    def get_valid_approval(
        self,
        *,
        workspace_id: uuid.UUID,
        plan_id: uuid.UUID,
        now: datetime | None = None,
    ) -> Approval:
        plan = self._session.get(Plan, plan_id)
        if plan is None or plan.workspace_id != workspace_id:
            raise OrchestratorError("plan not found", code="plan_not_found")

        approval = self._session.scalar(
            select(Approval)
            .where(
                Approval.workspace_id == workspace_id,
                Approval.plan_id == plan_id,
                Approval.status == "approved",
            )
            .order_by(Approval.created_at.desc())
            .limit(1)
        )
        if approval is None:
            raise ApprovalRequiredError()

        clock = now or _utcnow()
        expires = approval.expires_at
        if expires is not None:
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= clock:
                raise ApprovalExpiredError()

        if approval.plan_hash != plan.content_hash:
            raise PlanHashMismatchError()

        return approval

    # --- execute_plan ----------------------------------------------------------

    def execute_plan(
        self,
        *,
        workspace_id: uuid.UUID,
        plan_id: uuid.UUID,
        client_request_id: str,
        now: datetime | None = None,
        skip_write: bool = False,
        promote_registry_on_success: bool = False,
        actor_id: str | None = None,
    ) -> Operation:
        if not client_request_id or not client_request_id.strip():
            raise OrchestratorError(
                "client_request_id required for idempotent execute",
                code="client_request_id_required",
            )
        client_request_id = client_request_id.strip()

        # Viewer cannot execute writes when actor is registered (L-R21).
        if actor_id:
            try:
                RolesService(self._session).require_write(
                    workspace_id=workspace_id, actor_id=actor_id
                )
            except RoleDeniedError as exc:
                raise RoleForbiddenError(str(exc)) from exc

        existing = self._session.scalar(
            select(Operation).where(
                Operation.workspace_id == workspace_id,
                Operation.client_request_id == client_request_id,
            )
        )
        if existing is not None:
            return existing

        plan = self._session.get(Plan, plan_id)
        if plan is None or plan.workspace_id != workspace_id:
            raise OrchestratorError("plan not found", code="plan_not_found")

        # Fail closed without valid approval — zero WriteGuard calls.
        self.get_valid_approval(
            workspace_id=workspace_id, plan_id=plan_id, now=now
        )

        body = plan.body or {}
        try:
            validated = PlanVersion.model_validate(body)
        except ValidationError as exc:
            raise SchemaValidationError(
                f"stored plan schema invalid: {exc.errors()[0]['msg']}"
            ) from exc

        deploy_tools = frozenset({"create_project", "sources", "releases"})
        has_deploy = any(
            (s.tool_id or "") in deploy_tools and (s.params or {})
            for s in validated.steps
        )
        has_ops = any(
            (s.tool_id or "") in (OPS_WRITE_TOOLS | {"update_envs"})
            and (s.params or {})
            for s in validated.steps
        )
        has_deps = any(
            (s.tool_id or "") in DEP_WRITE_TOOLS and (s.params or {})
            for s in validated.steps
        )

        checkpoint: dict[str, Any] = {}
        state = OP_STATE_AWAITING_PROVIDER
        fingerprint: str | None = None

        # RecoveryBaseline before sensitive writes (monitor enable never substitutes).
        if not skip_write and (has_deploy or has_ops or has_deps):
            project_name = self._project_name_from_plan(validated)
            if project_name:
                MaintainService(self._session).capture_baseline(
                    workspace_id=workspace_id,
                    project_name=project_name,
                    case_id=plan.case_id,
                    snapshot={
                        "project_name": project_name,
                        "plan_id": str(plan.id),
                        "note": "pre_write_baseline",
                        "steps": [s.tool_id for s in validated.steps if s.tool_id],
                    },
                )

        if skip_write:
            checkpoint = {"mode": "skip_write", "provider_write": False}
        elif has_deps:
            client = self.resolve_liara_client(workspace_id)
            from app.services.write_guard import noop_provider_write

            if (
                client is not None
                and self.write_guard._provider_write is noop_provider_write  # noqa: SLF001
            ):
                self.write_guard = WriteGuard(liara_client=client)

            prior = self._latest_unknown_for_plan(workspace_id, plan.id)
            prior_cp = dict(prior.checkpoint or {}) if prior else {}
            registry = CapabilityRegistry(self._session)
            secrets = SecretService(self._session, self._settings)
            case = self._session.get(Case, plan.case_id)
            result = execute_dependency_steps(
                plan=validated,
                write_guard=self.write_guard,
                registry=registry,
                liara_client=client,
                secrets=secrets,
                workspace_id=workspace_id,
                case=case,
                prior_checkpoint=prior_cp,
                session=self._session,
            )
            checkpoint = result.to_checkpoint()
            # Attach GenUI dependency_plan from case if present.
            if case is not None and isinstance(case.constraints, dict):
                dep_plan = case.constraints.get("dependency_plan")
                if isinstance(dep_plan, dict):
                    checkpoint["dependency_plan"] = dep_plan
            state = result.state
            fingerprint = (
                result.attempts[0].fingerprint if result.attempts else None
            )
        elif has_ops:
            client = self.resolve_liara_client(workspace_id)
            from app.services.write_guard import noop_provider_write

            if (
                client is not None
                and self.write_guard._provider_write is noop_provider_write  # noqa: SLF001
            ):
                self.write_guard = WriteGuard(liara_client=client)

            prior = self._latest_unknown_for_plan(workspace_id, plan.id)
            prior_cp = dict(prior.checkpoint or {}) if prior else {}
            result = execute_ops_steps(
                plan=validated,
                write_guard=self.write_guard,
                liara_client=client,
                prior_checkpoint=prior_cp,
            )
            checkpoint = result.to_checkpoint()
            state = result.state
            fingerprint = (
                result.attempts[0].fingerprint if result.attempts else None
            )
            if promote_registry_on_success and result.write_count > 0:
                registry = CapabilityRegistry(self._session)
                registry.seed()
                updated = promote_ops_tools_tested(registry)
                checkpoint["registry_promoted"] = updated
            # Always reinforce env disabled when env steps present.
            if any((s.tool_id or "") == "update_envs" for s in validated.steps):
                registry = CapabilityRegistry(self._session)
                registry.seed()
                ensure_update_envs_disabled(registry)
                checkpoint.setdefault("open_needs", [])
                if ENV_OPEN_NEED not in checkpoint["open_needs"]:
                    checkpoint["open_needs"] = list(checkpoint["open_needs"]) + [
                        ENV_OPEN_NEED
                    ]
        elif has_deploy:
            client = self.resolve_liara_client(workspace_id)
            # Wire Liara into WriteGuard only when still on the default noop.
            from app.services.write_guard import noop_provider_write

            if (
                client is not None
                and self.write_guard._provider_write is noop_provider_write  # noqa: SLF001
            ):
                self.write_guard = WriteGuard(liara_client=client)

            # Prior unknown ops for same plan → seed provider_ids (no blind recreate).
            prior = self._latest_unknown_for_plan(workspace_id, plan.id)
            prior_cp = dict(prior.checkpoint or {}) if prior else {}

            result = execute_deploy_steps(
                plan=validated,
                write_guard=self.write_guard,
                liara_client=client,
                prior_checkpoint=prior_cp,
            )
            checkpoint = result.to_checkpoint()
            state = result.state
            fingerprint = (
                result.attempts[0].fingerprint if result.attempts else None
            )
            if (
                promote_registry_on_success
                and state == OP_STATE_DEPLOYED
                and result.provider_ids.get("releaseID")
            ):
                registry = CapabilityRegistry(self._session)
                registry.seed()
                updated = promote_deploy_tools_tested(registry)
                checkpoint["registry_promoted"] = updated
        else:
            # Stub / empty-params steps: record allowlisted intent via noop, no HTTP.
            for step in validated.steps:
                tool = step.tool_id or ""
                if tool not in ALLOWLISTED_WRITE_TOOLS:
                    continue
                self.write_guard.execute_allowlisted(
                    tool_id=tool,
                    payload={
                        "step_id": step.id,
                        "action": step.action,
                        "mode": "stub",
                        "effects": step.effects,
                        "name": f"stub-{step.id}",
                        "planID": "free",
                        "platform": "node",
                    }
                    if tool == "create_project"
                    else {
                        "step_id": step.id,
                        "action": step.action,
                        "mode": "stub",
                        "project_name": "stub",
                        "archive_path": "/dev/null",
                        "sourceID": "stub",
                        "port": 3000,
                        "platform": "node",
                    },
                )
            fingerprints = [
                hashlib.sha256(
                    f"{step.id}:{step.action}:{step.tool_id or ''}".encode()
                ).hexdigest()[:32]
                for step in validated.steps
            ]
            fingerprint = fingerprints[0] if fingerprints else None
            checkpoint = {
                "fingerprints": fingerprints,
                "mode": "execute_stub",
                "provider_write": False,
            }

        op = Operation(
            workspace_id=workspace_id,
            case_id=plan.case_id,
            plan_id=plan.id,
            client_request_id=client_request_id,
            fingerprint=fingerprint,
            state=state,
            checkpoint=checkpoint,
        )
        self._session.add(op)
        self._session.flush()
        self._audit(
            workspace_id,
            plan.case_id,
            "execute_plan",
            {
                "operation_id": str(op.id),
                "client_request_id": client_request_id,
                "state": op.state,
            },
        )
        return op

    def _latest_unknown_for_plan(
        self, workspace_id: uuid.UUID, plan_id: uuid.UUID
    ) -> Operation | None:
        return self._session.scalar(
            select(Operation)
            .where(
                Operation.workspace_id == workspace_id,
                Operation.plan_id == plan_id,
                Operation.state == OP_STATE_UNKNOWN,
            )
            .order_by(Operation.created_at.desc())
            .limit(1)
        )

    # --- Phase 3: collect_evidence / diagnose / fix options --------------------

    def _case_store(self, case: Case) -> dict[str, Any]:
        raw = case.constraints
        if isinstance(raw, dict):
            return dict(raw)
        return {}

    def _save_case_store(self, case: Case, store: dict[str, Any]) -> None:
        case.constraints = store
        self._session.flush()

    def collect_evidence(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        project_name: str,
        symptom: str | None = None,
        window_note: str | None = None,
    ) -> EvidencePack:
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        client = self.resolve_liara_client_for_read(workspace_id)
        pack = collect_evidence_from_client(
            client,
            project_name=project_name,
            symptom=symptom,
            window_note=window_note,
        )
        store = self._case_store(case)
        evidence = dict(store.get("evidence") or {})
        evidence[pack.version] = pack.model_dump(mode="json")
        store["evidence"] = evidence
        store["latest_evidence_version"] = pack.version
        self._save_case_store(case, store)

        # Promote evidence_reads documented → tested on successful mock/live read path
        if client is not None and (pack.facts or pack.gaps):
            registry = CapabilityRegistry(self._session)
            registry.seed()
            try:
                cap = registry.get("evidence_reads")
                if cap.status == "documented":
                    registry.set_status("evidence_reads", "tested")
            except Exception:  # noqa: BLE001 — registry optional for evidence
                pass

        self._audit(
            workspace_id,
            case.id,
            "evidence_collected",
            {
                "evidence_version": pack.version,
                "project_name": project_name,
                "gap_count": len(pack.gaps),
                "injection_stripped_count": pack.injection_stripped_count,
                "complete": pack.complete,
            },
        )
        return pack

    def get_evidence_pack(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        evidence_version: str,
    ) -> EvidencePack:
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        store = self._case_store(case)
        evidence = store.get("evidence") or {}
        raw = evidence.get(evidence_version) if isinstance(evidence, dict) else None
        if not isinstance(raw, dict):
            raise OrchestratorError(
                "evidence version not found", code="evidence_not_found"
            )
        try:
            return EvidencePack.model_validate(raw)
        except ValidationError as exc:
            raise SchemaValidationError(
                f"stored evidence invalid: {exc.errors()[0]['msg']}"
            ) from exc

    def diagnose(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        evidence_version: str,
        diagnosis_draft: dict[str, Any] | None = None,
    ) -> Diagnosis:
        """Build schema-validated diagnosis. Invalid draft → zero writes."""
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        pack = self.get_evidence_pack(
            workspace_id=workspace_id,
            case_id=case_id,
            evidence_version=evidence_version,
        )

        if diagnosis_draft is not None:
            try:
                diagnosis = Diagnosis.model_validate(diagnosis_draft)
            except ValidationError as exc:
                raise SchemaValidationError(
                    f"diagnosis schema invalid: {exc.errors()[0]['msg']}"
                ) from exc
            if diagnosis.evidence_version != evidence_version:
                raise SchemaValidationError(
                    "diagnosis.evidence_version must match request"
                )
        else:
            diagnosis = diagnose_from_evidence(pack)

        store = self._case_store(case)
        diagnoses = dict(store.get("diagnoses") or {})
        diagnoses[diagnosis.version] = diagnosis.model_dump(mode="json")
        store["diagnoses"] = diagnoses
        store["latest_diagnosis_version"] = diagnosis.version
        self._save_case_store(case, store)

        self._audit(
            workspace_id,
            case.id,
            "diagnosis_presented",
            {
                "diagnosis_version": diagnosis.version,
                "evidence_version": evidence_version,
                "hypothesis_count": len(diagnosis.hypotheses),
                "insufficient_evidence": diagnosis.insufficient_evidence,
            },
        )
        return diagnosis

    def propose_fix_options(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        diagnosis_version: str,
        project_name: str,
        plan_id_for_resize: str | None = None,
    ) -> FixOptionsPayload:
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        store = self._case_store(case)
        diagnoses = store.get("diagnoses") or {}
        raw = diagnoses.get(diagnosis_version) if isinstance(diagnoses, dict) else None
        if not isinstance(raw, dict):
            raise OrchestratorError(
                "diagnosis version not found", code="diagnosis_not_found"
            )
        try:
            diagnosis = Diagnosis.model_validate(raw)
        except ValidationError as exc:
            raise SchemaValidationError(
                f"stored diagnosis invalid: {exc.errors()[0]['msg']}"
            ) from exc

        registry = CapabilityRegistry(self._session)
        registry.seed()
        ensure_update_envs_disabled(registry)
        status_map: dict[str, str] = {}
        for tool_id in ("restart_resize", "update_envs", "evidence_reads"):
            try:
                status_map[tool_id] = registry.get(tool_id).status
            except Exception:  # noqa: BLE001
                continue

        payload = build_fix_options(
            diagnosis,
            project_name=project_name,
            registry_status=status_map,
            plan_id_for_resize=plan_id_for_resize,
        )
        store["latest_fix_options"] = payload.model_dump(mode="json")
        self._save_case_store(case, store)
        self._audit(
            workspace_id,
            case.id,
            "fix_options_presented",
            {
                "diagnosis_version": diagnosis_version,
                "option_ids": [o.id for o in payload.options],
                "open_needs": payload.open_needs,
            },
        )
        return payload

    def create_plan_from_fix_option(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        option_id: str,
    ) -> tuple[Plan, PlanVersion]:
        """Turn an enabled fix option into an ops plan (still needs approve+execute)."""
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        store = self._case_store(case)
        raw = store.get("latest_fix_options")
        if not isinstance(raw, dict):
            raise OrchestratorError(
                "fix options not found — call propose_fix_options first",
                code="fix_options_not_found",
            )
        payload = FixOptionsPayload.model_validate(raw)
        option = next((o for o in payload.options if o.id == option_id), None)
        if option is None:
            raise OrchestratorError("fix option not found", code="fix_option_not_found")
        if not option.enabled:
            raise OrchestratorError(
                option.disabled_reason or "fix option disabled",
                code="fix_option_disabled",
            )
        ops_cfg = fix_option_to_ops_cfg(option)
        if not ops_cfg:
            raise OrchestratorError(
                "fix option cannot map to ops plan",
                code="fix_option_not_executable",
            )
        return self.create_plan(
            workspace_id=workspace_id,
            case_id=case_id,
            ops=ops_cfg,
        )

    def verify_fix(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        operation_id: uuid.UUID,
        method: str = "get_project_health",
        project_name: str | None = None,
    ) -> FixVerification:
        """Same-method before/after; L-AC17 — never auto-chains another write."""
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        op = self._require_operation(workspace_id, operation_id)
        writes_before = self.write_guard.call_count

        checkpoint = dict(op.checkpoint or {})
        provider_ids = dict(checkpoint.get("provider_ids") or {})
        name = (
            project_name
            or provider_ids.get("project_name")
            or (checkpoint.get("project_name") if isinstance(checkpoint.get("project_name"), str) else None)
        )
        if not name:
            raise OrchestratorError(
                "project_name required for fix verification",
                code="project_name_required",
            )

        before = checkpoint.get("health") if isinstance(checkpoint.get("health"), dict) else None
        client = self.resolve_liara_client_for_read(workspace_id)
        verification = verify_fix_same_method(
            client,
            project_name=str(name),
            method=method,
            before=before,
        )

        # Hard ban: do not schedule or execute another write here.
        policy = refuse_autonomous_next_write(
            verification,
            write_guard_call_count_before=writes_before,
            write_guard_call_count_after=self.write_guard.call_count,
        )

        checkpoint["fix_verification"] = verification.model_dump(mode="json")
        checkpoint["autonomous_next_write"] = False
        open_needs = list(checkpoint.get("open_needs") or [])
        if verification.open_need and verification.open_need not in open_needs:
            open_needs.append(verification.open_need)
        checkpoint["open_needs"] = open_needs
        op.checkpoint = checkpoint
        if verification.effective is False:
            op.state = OP_STATE_BLOCKED
        self._session.flush()

        store = self._case_store(case)
        store["latest_fix_verification"] = {
            **verification.model_dump(mode="json"),
            "policy": policy,
        }
        self._save_case_store(case, store)

        self._audit(
            workspace_id,
            case.id,
            "verification_completed",
            {
                "operation_id": str(op.id),
                "effective": verification.effective,
                "open_need": verification.open_need,
                "autonomous_next_write": False,
                "write_delta": policy["write_delta"],
            },
        )
        return verification

    # --- Phase 5: create_patch / sandbox / separate approvals ------------------

    def create_patch(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        evidence_version: str,
        diagnosis_version: str,
        app_path: str,
        hypothesis_id: str | None = None,
        unified_diff: str | None = None,
        rationale: str | None = None,
    ) -> PatchDiffPayload:
        """Propose a limited patch tied to evidence/diagnosis — no provider write."""
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        # Validate evidence + diagnosis exist and match.
        _ = self.get_evidence_pack(
            workspace_id=workspace_id,
            case_id=case_id,
            evidence_version=evidence_version,
        )
        store = self._case_store(case)
        diagnoses = store.get("diagnoses") or {}
        raw = diagnoses.get(diagnosis_version) if isinstance(diagnoses, dict) else None
        if not isinstance(raw, dict):
            raise OrchestratorError(
                "diagnosis version not found", code="diagnosis_not_found"
            )
        try:
            diagnosis = Diagnosis.model_validate(raw)
        except ValidationError as exc:
            raise SchemaValidationError(
                f"stored diagnosis invalid: {exc.errors()[0]['msg']}"
            ) from exc
        if diagnosis.evidence_version != evidence_version:
            raise OrchestratorError(
                "diagnosis.evidence_version does not match request",
                code="evidence_diagnosis_mismatch",
            )

        root = Path(app_path).expanduser().resolve()
        try:
            patch = create_patch_proposal(
                evidence_version=evidence_version,
                diagnosis_version=diagnosis_version,
                hypothesis_id=hypothesis_id,
                app_root=root,
                unified_diff=unified_diff,
                rationale=rationale,
            )
        except ValueError as exc:
            raise OrchestratorError(str(exc), code="patch_invalid") from exc

        patches = dict(store.get("patches") or {})
        patches[patch.version] = patch.model_dump(mode="json")
        store["patches"] = patches
        store["latest_patch_version"] = patch.version
        store.pop("latest_sandbox", None)  # invalidate prior sandbox on new patch
        store.pop("patch_record_approval", None)
        store.pop("release_approval", None)
        self._save_case_store(case, store)

        self._audit(
            workspace_id,
            case.id,
            "patch_created",
            {
                "patch_version": patch.version,
                "evidence_version": evidence_version,
                "diagnosis_version": diagnosis_version,
                "files_changed": patch.files_changed,
                "content_hash": patch.content_hash,
            },
        )
        return self._patch_diff_payload(case, patch)

    def run_patch_sandbox(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        patch_version: str,
        network_policy_available: bool | None = None,
        command_key: str = "pytest_fixture",
    ) -> PatchDiffPayload:
        """Apply patch on temp copy + scrubbed env; red tests ≠ ready_for_release."""
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        patch = self._get_patch(case, patch_version)
        if not patch.base_path:
            raise OrchestratorError(
                "patch missing base_path", code="patch_base_path_missing"
            )
        root = Path(patch.base_path)
        if not root.is_dir():
            raise OrchestratorError(
                "patch base_path not found", code="patch_base_path_missing"
            )

        writes_before = self.write_guard.call_count
        outcome = run_sandbox(
            app_root=root,
            unified_diff=patch.unified_diff,
            command_key=command_key,
            network_policy_available=network_policy_available,
        )
        if self.write_guard.call_count != writes_before:
            raise OrchestratorError(
                "sandbox must not trigger WriteGuard",
                code="sandbox_write_guard_violation",
            )

        store = self._case_store(case)
        store["latest_sandbox"] = {
            "patch_version": patch.version,
            **outcome.result.model_dump(mode="json"),
        }
        # Persist sandbox on a lightweight operation checkpoint for resume/UI.
        op = Operation(
            workspace_id=workspace_id,
            case_id=case.id,
            plan_id=None,
            client_request_id=f"sandbox-{patch.version}-{uuid.uuid4().hex[:8]}",
            fingerprint=patch.content_hash,
            state="sandbox_passed" if outcome.result.passed else "sandbox_failed",
            checkpoint={
                "kind": "patch_sandbox",
                "patch_version": patch.version,
                "sandbox": outcome.result.model_dump(mode="json"),
                "ready_for_release": outcome.result.ready_for_release,
            },
        )
        self._session.add(op)
        self._save_case_store(case, store)

        # Promote sandbox_run documented → tested on successful mock run path.
        registry = CapabilityRegistry(self._session)
        registry.seed()
        try:
            cap = registry.get("sandbox_run")
            if cap.status == "documented":
                registry.set_status("sandbox_run", "tested")
        except Exception:  # noqa: BLE001 — registry optional
            pass

        self._audit(
            workspace_id,
            case.id,
            "sandbox_completed",
            {
                "patch_version": patch.version,
                "passed": outcome.result.passed,
                "ready_for_release": outcome.result.ready_for_release,
                "network_isolated": outcome.result.network_isolated,
                "secrets_scrubbed": outcome.result.secrets_scrubbed,
                "operation_id": str(op.id),
            },
        )
        return self._patch_diff_payload(case, patch)

    def approve_patch_record(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        patch_version: str,
        expires_at: datetime | None = None,
    ) -> tuple[Plan, Approval, PatchDiffPayload]:
        """HITL gate to record the patch — does NOT authorize Liara release."""
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        patch = self._get_patch(case, patch_version)
        plan_body = build_patch_record_plan(patch=patch)
        plan, _validated = self.create_plan(
            workspace_id=workspace_id,
            case_id=case_id,
            plan_draft=plan_body,
        )
        approval = self.approve_plan(
            workspace_id=workspace_id,
            plan_id=plan.id,
            scope=patch_record_scope(patch.version, patch.content_hash),
            expires_at=expires_at,
        )
        store = self._case_store(case)
        store["patch_record_approval"] = {
            "approval_id": str(approval.id),
            "plan_id": str(plan.id),
            "patch_version": patch.version,
            "kind": APPROVAL_KIND_PATCH_RECORD,
            "status": approval.status,
        }
        self._save_case_store(case, store)
        self._audit(
            workspace_id,
            case.id,
            "approve_patch_record",
            {
                "approval_id": str(approval.id),
                "plan_id": str(plan.id),
                "patch_version": patch.version,
                "kind": APPROVAL_KIND_PATCH_RECORD,
            },
        )
        return plan, approval, self._patch_diff_payload(case, patch)

    def approve_release(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        patch_version: str,
        project_name: str,
        archive_path: str,
        port: int = 3000,
        platform: str = "node",
        expires_at: datetime | None = None,
    ) -> tuple[Plan, Approval, PatchDiffPayload]:
        """Separate release approval — refused when sandbox not ready_for_release."""
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        patch = self._get_patch(case, patch_version)
        store = self._case_store(case)
        sandbox_raw = store.get("latest_sandbox")
        if not isinstance(sandbox_raw, dict) or sandbox_raw.get("patch_version") != (
            patch.version
        ):
            raise OrchestratorError(
                "sandbox result required before release approval",
                code="sandbox_required",
            )
        try:
            sandbox = PatchSandboxResult.model_validate(
                {k: v for k, v in sandbox_raw.items() if k != "patch_version"}
            )
        except ValidationError as exc:
            raise SchemaValidationError(
                f"stored sandbox invalid: {exc.errors()[0]['msg']}"
            ) from exc

        # Hard ban: red tests / non-isolated ⇒ no release approval (L-AC37/46).
        if not sandbox.ready_for_release:
            raise OrchestratorError(
                "release approval blocked — sandbox not ready_for_release "
                "(red tests, missing network isolation, or scrub failure)",
                code="release_blocked_sandbox",
            )
        if not sandbox.passed:
            raise OrchestratorError(
                "release approval blocked — sandbox tests did not pass",
                code="release_blocked_red_tests",
            )

        record = store.get("patch_record_approval")
        if not isinstance(record, dict) or record.get("status") != "approved":
            raise OrchestratorError(
                "approve_patch_record required before approve_release",
                code="patch_record_required",
            )
        if record.get("patch_version") != patch.version:
            raise OrchestratorError(
                "patch_record approval is for a different patch version",
                code="patch_record_mismatch",
            )

        plan_body = build_release_plan_from_patch(
            patch=patch,
            project_name=project_name,
            archive_path=archive_path,
            port=port,
            platform=platform,
        )
        plan, _validated = self.create_plan(
            workspace_id=workspace_id,
            case_id=case_id,
            plan_draft=plan_body,
        )
        approval = self.approve_plan(
            workspace_id=workspace_id,
            plan_id=plan.id,
            scope=release_scope(patch.version, patch.content_hash),
            expires_at=expires_at,
        )
        # Ensure kinds remain distinct from patch_record.
        if approval_kind_of(approval.scope) != APPROVAL_KIND_RELEASE:
            raise OrchestratorError(
                "release approval kind mismatch",
                code="approval_kind_mismatch",
            )
        store = self._case_store(case)
        store["release_approval"] = {
            "approval_id": str(approval.id),
            "plan_id": str(plan.id),
            "patch_version": patch.version,
            "kind": APPROVAL_KIND_RELEASE,
            "status": approval.status,
        }
        self._save_case_store(case, store)
        self._audit(
            workspace_id,
            case.id,
            "approve_release",
            {
                "approval_id": str(approval.id),
                "plan_id": str(plan.id),
                "patch_version": patch.version,
                "kind": APPROVAL_KIND_RELEASE,
            },
        )
        return plan, approval, self._patch_diff_payload(case, patch)

    def get_patch_diff(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        patch_version: str | None = None,
    ) -> PatchDiffPayload:
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        store = self._case_store(case)
        version = patch_version or store.get("latest_patch_version")
        if not isinstance(version, str):
            raise OrchestratorError("patch not found", code="patch_not_found")
        patch = self._get_patch(case, version)
        return self._patch_diff_payload(case, patch)

    def _get_patch(self, case: Case, patch_version: str) -> PatchProposal:
        store = self._case_store(case)
        patches = store.get("patches") or {}
        raw = patches.get(patch_version) if isinstance(patches, dict) else None
        if not isinstance(raw, dict):
            raise OrchestratorError("patch not found", code="patch_not_found")
        try:
            return PatchProposal.model_validate(raw)
        except ValidationError as exc:
            raise SchemaValidationError(
                f"stored patch invalid: {exc.errors()[0]['msg']}"
            ) from exc

    def _patch_diff_payload(
        self, case: Case, patch: PatchProposal
    ) -> PatchDiffPayload:
        store = self._case_store(case)
        sandbox: PatchSandboxResult | None = None
        raw_sb = store.get("latest_sandbox")
        if (
            isinstance(raw_sb, dict)
            and raw_sb.get("patch_version") == patch.version
        ):
            try:
                sandbox = PatchSandboxResult.model_validate(
                    {k: v for k, v in raw_sb.items() if k != "patch_version"}
                )
            except ValidationError:
                sandbox = None

        record = store.get("patch_record_approval")
        release = store.get("release_approval")
        patch_recorded = (
            isinstance(record, dict)
            and record.get("status") == "approved"
            and record.get("patch_version") == patch.version
        )
        release_ok = (
            isinstance(release, dict)
            and release.get("status") == "approved"
            and release.get("patch_version") == patch.version
        )
        open_needs: list[str] = []
        if sandbox is None:
            open_needs.append("sandbox_not_run")
        elif not sandbox.passed:
            open_needs.append("sandbox_tests_red")
        elif not sandbox.network_isolated:
            open_needs.append("sandbox_network_policy_unavailable")
        elif not sandbox.ready_for_release:
            open_needs.append("sandbox_not_ready_for_release")
        if not patch_recorded:
            open_needs.append("patch_record_approval_required")
        can_release = bool(
            sandbox
            and sandbox.ready_for_release
            and sandbox.passed
            and patch_recorded
            and not release_ok
        )
        summary = (
            f"Patch {patch.version}: "
            f"{'sandbox green' if sandbox and sandbox.passed else 'sandbox pending/red'}; "
            f"record={'yes' if patch_recorded else 'no'}; "
            f"release={'yes' if release_ok else 'blocked' if not can_release else 'awaiting'}"
        )
        return PatchDiffPayload(
            patch=patch,
            sandbox=sandbox,
            patch_record_approved=patch_recorded,
            release_approved=release_ok,
            can_approve_release=can_release,
            open_needs=open_needs,
            summary=summary,
        )

    # --- continue_or_stop / verify ---------------------------------------------

    def continue_or_stop(
        self,
        *,
        workspace_id: uuid.UUID,
        operation_id: uuid.UUID,
        decision: str,
    ) -> Operation:
        op = self._require_operation(workspace_id, operation_id)
        if decision not in ("continue", "stop"):
            raise OrchestratorError(
                "decision must be continue|stop", code="invalid_decision"
            )
        if decision == "stop":
            op.state = OP_STATE_BLOCKED
        else:
            if op.state in (OP_STATE_AWAITING_PROVIDER, OP_STATE_UNKNOWN):
                op.state = OP_STATE_PLANNED
        self._session.flush()
        self._audit(
            workspace_id,
            op.case_id,
            "continue_or_stop",
            {"operation_id": str(op.id), "decision": decision, "state": op.state},
        )
        return op

    def verify_result(
        self,
        *,
        workspace_id: uuid.UUID,
        operation_id: uuid.UUID,
        app_url: str | None = None,
        http_get: Any | None = None,
    ) -> Operation:
        op = self._require_operation(workspace_id, operation_id)
        checkpoint = dict(op.checkpoint or {})
        provider_ids = dict(checkpoint.get("provider_ids") or {})

        # Phase-4: never claim complete success with required/pending deps.
        case = self._session.get(Case, op.case_id) if op.case_id else None
        constraints = (
            case.constraints if case is not None and isinstance(case.constraints, dict) else {}
        )
        pending = list(
            checkpoint.get("pending_resources")
            or constraints.get("pending_resources")
            or []
        )
        dep_open = list(checkpoint.get("open_needs") or constraints.get("open_needs") or [])
        dep_blocks = bool(pending) or any(
            n
            in (
                "dependency_create_ld05_unproven",
                "required_dependency_missing",
                "dependency_resource_incomplete",
            )
            for n in dep_open
        ) or checkpoint.get("can_claim_complete_success") is False

        if checkpoint.get("mode") == "phase4_dependencies" or dep_blocks:
            checkpoint["verified_at"] = _utcnow().isoformat()
            checkpoint["verify_mode"] = "phase4_dependencies"
            checkpoint["complete_success"] = False if dep_blocks else True
            if dep_blocks:
                checkpoint.setdefault("open_needs", dep_open)
                op.checkpoint = checkpoint
                op.state = OP_STATE_BLOCKED
            elif provider_ids.get("databaseID") or provider_ids.get("disks"):
                checkpoint["complete_success"] = True
                op.checkpoint = checkpoint
                op.state = OP_STATE_VERIFIED
            else:
                op.checkpoint = checkpoint
                op.state = OP_STATE_VERIFIED_STUB
        elif provider_ids.get("releaseID") or checkpoint.get("mode") == "phase1_deploy":
            client = self.resolve_liara_client(workspace_id)
            verification = verify_deploy(
                provider_ids=provider_ids,
                liara_client=client,
                app_url=app_url or provider_ids.get("app_url"),
                http_get=http_get,
            )
            # Required deps from case still block "complete" even if release ok.
            if dep_blocks:
                verification = dict(verification)
                verification["ok"] = False
                verification["complete_success"] = False
                verification["blocked_by_dependencies"] = True
                checkpoint["open_needs"] = dep_open
            checkpoint["verification"] = verification
            checkpoint["verified_at"] = verification.get("verified_at")
            checkpoint["complete_success"] = bool(
                verification.get("ok") and not dep_blocks
            )
            op.checkpoint = checkpoint
            op.state = (
                OP_STATE_VERIFIED if verification.get("ok") else OP_STATE_VERIFY_FAILED
            )
        else:
            # Legacy stub path (no provider deploy ids).
            checkpoint["verified_at"] = _utcnow().isoformat()
            checkpoint["verify_mode"] = "stub"
            if dep_blocks:
                checkpoint["complete_success"] = False
                checkpoint["open_needs"] = dep_open
                op.checkpoint = checkpoint
                op.state = OP_STATE_BLOCKED
            else:
                op.checkpoint = checkpoint
                op.state = OP_STATE_VERIFIED_STUB

        self._session.flush()
        self._audit(
            workspace_id,
            op.case_id,
            "verify_result",
            {"operation_id": str(op.id), "state": op.state},
        )
        return op

    def operation_payload(self, op: Operation) -> OperationPayload:
        fps: list[str] = []
        if op.checkpoint and isinstance(op.checkpoint.get("fingerprints"), list):
            fps = [str(x) for x in op.checkpoint["fingerprints"]]
        elif op.fingerprint:
            fps = [op.fingerprint]
        return OperationPayload(
            id=op.id,
            state=op.state,
            fingerprints=fps,
            client_request_id=op.client_request_id,
            plan_id=op.plan_id,
            case_id=op.case_id,
            checkpoint=op.checkpoint,
        )

    def get_operation(
        self,
        *,
        workspace_id: uuid.UUID,
        operation_id: uuid.UUID | None = None,
        client_request_id: str | None = None,
    ) -> Operation:
        """Load durable Operation by id or client_request_id (session resume)."""
        if operation_id is not None:
            return self._require_operation(workspace_id, operation_id)
        if client_request_id and client_request_id.strip():
            op = self._session.scalar(
                select(Operation).where(
                    Operation.workspace_id == workspace_id,
                    Operation.client_request_id == client_request_id.strip(),
                )
            )
            if op is None:
                raise OrchestratorError(
                    "operation not found", code="operation_not_found"
                )
            return op
        raise OrchestratorError(
            "operation_id or client_request_id required",
            code="operation_lookup_required",
        )

    def resume_operation(
        self,
        *,
        workspace_id: uuid.UUID,
        operation_id: uuid.UUID | None = None,
        client_request_id: str | None = None,
    ) -> Operation:
        """Session/worker resume: load Operation; never re-issue provider writes."""
        op = self.get_operation(
            workspace_id=workspace_id,
            operation_id=operation_id,
            client_request_id=client_request_id,
        )
        checkpoint = dict(op.checkpoint or {})
        checkpoint["resumed_at"] = _utcnow().isoformat()
        checkpoint["resume"] = {
            "mode": "load_only",
            "duplicate_write": False,
            "write_guard_calls": self.write_guard.call_count,
        }
        op.checkpoint = checkpoint
        self._session.flush()
        self._audit(
            workspace_id,
            op.case_id,
            "resume_operation",
            {
                "operation_id": str(op.id),
                "client_request_id": op.client_request_id,
                "state": op.state,
                "duplicate_write": False,
            },
        )
        return op

    def _require_operation(
        self, workspace_id: uuid.UUID, operation_id: uuid.UUID
    ) -> Operation:
        op = self._session.get(Operation, operation_id)
        if op is None or op.workspace_id != workspace_id:
            raise OrchestratorError(
                "operation not found", code="operation_not_found"
            )
        return op

    def _audit(
        self,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        self._session.add(
            AuditEvent(
                workspace_id=workspace_id,
                case_id=case_id,
                event_type=f"orchestrator.{event_type}",
                payload=payload,
                actor="orchestrator",
            )
        )

    @staticmethod
    def _project_name_from_plan(plan: PlanVersion) -> str | None:
        for step in plan.steps:
            params = step.params or {}
            name = params.get("project_name") or params.get("name") or params.get(
                "project"
            )
            if name:
                return str(name)
        return None

    # --- Phase 6: maintain / recovery / roles --------------------------------

    def maintain(self) -> MaintainService:
        return MaintainService(self._session)

    def roles(self) -> RolesService:
        return RolesService(self._session)

    def enable_monitor(
        self,
        *,
        workspace_id: uuid.UUID,
        target: str,
        case_id: uuid.UUID | None = None,
        interval_seconds: int = 60,
        criteria: dict[str, Any] | None = None,
        notification_allowed: bool = True,
        monitor_id: uuid.UUID | None = None,
        actor_id: str | None = None,
    ) -> MonitorStatusPayload:
        if actor_id:
            try:
                self.roles().require_write(
                    workspace_id=workspace_id, actor_id=actor_id
                )
            except RoleDeniedError as exc:
                raise RoleForbiddenError(str(exc)) from exc
        try:
            mon = self.maintain().enable_monitor(
                workspace_id=workspace_id,
                target=target,
                case_id=case_id,
                interval_seconds=interval_seconds,
                criteria=criteria,
                notification_allowed=notification_allowed,
                monitor_id=monitor_id,
            )
        except ValueError as exc:
            raise OrchestratorError(str(exc), code="monitor_invalid") from exc
        status = monitor_to_status(mon)
        # Hard invariant: enable never grants write.
        assert status.grants_write_permission is False
        return status

    def disable_monitor(
        self,
        *,
        workspace_id: uuid.UUID,
        monitor_id: uuid.UUID,
        actor_id: str | None = None,
    ) -> MonitorStatusPayload:
        if actor_id:
            try:
                self.roles().require_write(
                    workspace_id=workspace_id, actor_id=actor_id
                )
            except RoleDeniedError as exc:
                raise RoleForbiddenError(str(exc)) from exc
        try:
            mon = self.maintain().disable_monitor(
                workspace_id=workspace_id, monitor_id=monitor_id
            )
        except LookupError as exc:
            raise OrchestratorError(str(exc), code="monitor_not_found") from exc
        return monitor_to_status(mon)

    def run_monitor_check(
        self,
        *,
        workspace_id: uuid.UUID,
        monitor_id: uuid.UUID,
        now: datetime | None = None,
        check_fn: Any | None = None,
    ) -> dict[str, Any]:
        svc = MaintainService(self._session, periodic_check=check_fn) if check_fn else self.maintain()
        try:
            mon, incident = svc.run_periodic_check(
                workspace_id=workspace_id, monitor_id=monitor_id, now=now
            )
        except LookupError as exc:
            raise OrchestratorError(str(exc), code="monitor_not_found") from exc
        except ValueError as exc:
            raise OrchestratorError(str(exc), code="monitor_invalid") from exc
        out: dict[str, Any] = {
            "monitor": monitor_to_status(mon).model_dump(mode="json"),
            "incident": (
                incident_to_card(incident).model_dump(mode="json") if incident else None
            ),
            # Explicit product invariant for clients/tests.
            "monitor_grants_write": False,
            "incident_grants_write": False,
        }
        return out

    def resolve_incident(
        self,
        *,
        workspace_id: uuid.UUID,
        incident_id: uuid.UUID,
        evidence: str,
        actor_id: str | None = None,
    ) -> IncidentCardPayload:
        if actor_id:
            try:
                self.roles().require_write(
                    workspace_id=workspace_id, actor_id=actor_id
                )
            except RoleDeniedError as exc:
                raise RoleForbiddenError(str(exc)) from exc
        try:
            inc = self.maintain().resolve_incident(
                workspace_id=workspace_id,
                incident_id=incident_id,
                evidence=evidence,
            )
        except LookupError as exc:
            raise OrchestratorError(str(exc), code="incident_not_found") from exc
        except ValueError as exc:
            raise OrchestratorError(str(exc), code="incident_invalid") from exc
        return incident_to_card(inc)

    def create_recovery_plan(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID,
        project_name: str,
        action: str = "restart",
        baseline_id: uuid.UUID | None = None,
        actor_id: str | None = None,
    ) -> tuple[Plan, PlanVersion, RecoveryPlanPayload]:
        """Draft recovery plan — does NOT execute; fresh approve_plan required."""
        if actor_id:
            try:
                self.roles().require_write(
                    workspace_id=workspace_id, actor_id=actor_id
                )
            except RoleDeniedError as exc:
                raise RoleForbiddenError(str(exc)) from exc
        self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        try:
            plan_body, view, _baseline = self.maintain().build_recovery_plan(
                workspace_id=workspace_id,
                project_name=project_name,
                case_id=case_id,
                action=action,
                baseline_id=baseline_id,
            )
        except LookupError as exc:
            raise OrchestratorError(str(exc), code="baseline_not_found") from exc
        except ValueError as exc:
            raise OrchestratorError(str(exc), code="recovery_invalid") from exc

        plan, validated = self.create_plan(
            workspace_id=workspace_id,
            case_id=case_id,
            plan_draft=plan_body.model_dump(mode="json"),
        )
        # Persist GenUI recovery_plan on case store.
        case = self.ensure_case(workspace_id=workspace_id, case_id=case_id)
        store = self._case_store(case)
        store["recovery_plan"] = view.model_dump(mode="json")
        self._save_case_store(case, store)
        self._audit(
            workspace_id,
            case_id,
            "recovery_plan_drafted",
            {
                "plan_id": str(plan.id),
                "baseline_id": view.baseline_id,
                "requires_fresh_approval": True,
                "monitor_enable_authorizes": False,
            },
        )
        return plan, validated, view

    def list_audit_events(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.maintain().list_audit_events(
            workspace_id=workspace_id, case_id=case_id, limit=limit
        )

    def seed_adapter_registry(self) -> list[str]:
        registry = CapabilityRegistry(self._session)
        return ensure_documented_adapters(registry)

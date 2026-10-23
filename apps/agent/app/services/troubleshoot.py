"""Phase-3 troubleshoot — evidence, structured diagnosis, direct-fix options.

Hard rules (L-R07, L-AC13/14/17):
- Sanitize logs/events before any LLM-facing path; injection text never becomes tools.
- Diagnosis separates facts / hypotheses / gaps; no invented confidence percentages.
- Missing metrics → data gap, never empty success.
- Direct fixes reuse approval + WriteGuard; update_envs stays disabled (L-D03).
- After ineffective fix: open-need, zero autonomous next write.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from app.schemas.orchestration import (
    Diagnosis,
    EvidenceFact,
    EvidenceGap,
    EvidencePack,
    FixOption,
    FixOptionsPayload,
    FixVerification,
    Hypothesis,
)
from app.services.liara_client import LiaraClient, LiaraClientError, sanitize_for_log
from app.services.ops import ENV_OPEN_NEED, post_action_health
from app.services.write_guard import ALLOWLISTED_WRITE_TOOLS, OPS_WRITE_TOOLS

# Patterns that look like prompt injection / fake tool calls in provider logs.
_INJECTION_RE = re.compile(
    r"(?is)("
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts)|"
    r"system\s*:\s*|</?\s*system\s*>|"
    r"(do\s+not\s+)?execute\s+(tool|write|plan)|"
    r"tool_id\s*[:=]\s*[\"']?\w+|"
    r"call\s+writeguard|"
    r"\{[^{}]{0,80}\"tool_id\"[^{}]{0,80}\}"
    r")"
)

# Direct-fix tools phase-3 may propose (still need approval + registry status).
DIRECT_FIX_TOOLS = frozenset({"restart", "resize"})
# Env + dependency reconnect are options but gated.
GATED_FIX_TOOLS = frozenset({"update_envs", "dependency_reconnect"})

OPEN_NEED_INEFFECTIVE = "fix_ineffective_no_autonomous_retry"
OPEN_NEED_INSUFFICIENT_AFTER = "verification_after_data_insufficient"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_version(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sanitize_log_line(message: str | None) -> tuple[str, bool]:
    """Redact secrets + strip injection; return (clean, was_injection)."""
    if not message:
        return "", False
    stripped = _INJECTION_RE.sub("[injection-stripped]", message)
    was_injection = stripped != message
    cleaned = sanitize_for_log(stripped, limit=400)
    return cleaned, was_injection


def sanitize_log_excerpts(
    logs: list[dict[str, Any]], *, limit: int = 40
) -> tuple[list[str], int]:
    """Build LLM-safe excerpts; count stripped injection attempts."""
    excerpts: list[str] = []
    stripped = 0
    for entry in logs[:limit]:
        raw = entry.get("message")
        if not isinstance(raw, str):
            continue
        clean, was = sanitize_log_line(raw)
        if was:
            stripped += 1
        if clean:
            excerpts.append(clean)
    return excerpts, stripped


def _metrics_present(payload: dict[str, Any] | list[Any] | None) -> bool:
    if payload is None:
        return False
    if isinstance(payload, list):
        return len(payload) > 0
    if isinstance(payload, dict):
        # Empty object or explicit null series → gap
        if not payload:
            return False
        for key in ("data", "metrics", "values", "series", "points"):
            val = payload.get(key)
            if isinstance(val, list) and len(val) > 0:
                return True
            if isinstance(val, dict) and val:
                return True
        # Non-empty dict without known series keys — treat as present but thin
        return True
    return False


def collect_evidence_from_client(
    client: LiaraClient | None,
    *,
    project_name: str,
    symptom: str | None = None,
    window_note: str | None = None,
) -> EvidencePack:
    """Read status/logs/events/cpu/memory; record gaps; sanitize logs."""
    facts: list[EvidenceFact] = []
    gaps: list[EvidenceGap] = []
    sanitized: list[str] = []
    injection_count = 0
    fact_i = 0

    def _fid() -> str:
        nonlocal fact_i
        fact_i += 1
        return f"f{fact_i}"

    if client is None:
        gaps.append(
            EvidenceGap(
                source="client",
                reason="no_liara_client",
                impact="Cannot collect provider evidence; diagnosis will be insufficient.",
            )
        )
        body = {
            "project_name": project_name,
            "symptom": symptom,
            "gaps": [g.model_dump() for g in gaps],
        }
        return EvidencePack(
            version=_content_version(body),
            project_name=project_name,
            symptom=symptom,
            window_note=window_note,
            collected_at=_utcnow_iso(),
            facts=[],
            gaps=gaps,
            sanitized_log_excerpts=[],
            injection_stripped_count=0,
            complete=False,
        )

    # Status
    try:
        project = client.get_project(project_name)
        status = str(project.get("status") or "")
        facts.append(
            EvidenceFact(
                id=_fid(),
                source="status",
                summary=f"project status={status or 'unknown'} isDeployed={project.get('isDeployed')}",
                observed_at=_utcnow_iso(),
                raw_ref=f"project:{project_name}:status",
            )
        )
    except LiaraClientError as exc:
        gaps.append(
            EvidenceGap(
                source="status",
                reason=exc.code,
                impact="App status unavailable; cannot confirm running state.",
            )
        )

    # Logs
    try:
        logs = client.get_logs(project_name)
        sanitized, injection_count = sanitize_log_excerpts(logs)
        if not logs:
            gaps.append(
                EvidenceGap(
                    source="logs",
                    reason="empty",
                    impact="No log lines; runtime errors may be invisible.",
                )
            )
        else:
            # Summarize without raw injection text
            errorish = [
                e
                for e in sanitized
                if re.search(r"(?i)\b(error|exception|fatal|oom|killed)\b", e)
            ]
            facts.append(
                EvidenceFact(
                    id=_fid(),
                    source="logs",
                    summary=(
                        f"{len(logs)} log lines; {len(errorish)} error-like after sanitize; "
                        f"{injection_count} injection fragments stripped"
                    ),
                    observed_at=_utcnow_iso(),
                    raw_ref=f"project:{project_name}:logs",
                )
            )
            if errorish:
                facts.append(
                    EvidenceFact(
                        id=_fid(),
                        source="logs",
                        summary=f"recent error-like: {errorish[-1][:200]}",
                        observed_at=_utcnow_iso(),
                        raw_ref=f"project:{project_name}:logs:error",
                    )
                )
    except LiaraClientError as exc:
        gaps.append(
            EvidenceGap(
                source="logs",
                reason=exc.code,
                impact="Logs unavailable; do not invent error messages.",
            )
        )

    # Events
    try:
        events = client.get_events(project_name)
        if not events:
            gaps.append(
                EvidenceGap(
                    source="events",
                    reason="empty",
                    impact="No lifecycle events; restarts/deploys may be unknown.",
                )
            )
        else:
            last = events[-1]
            kind = last.get("type") or last.get("action") or last.get("name") or "event"
            facts.append(
                EvidenceFact(
                    id=_fid(),
                    source="events",
                    summary=f"{len(events)} events; latest={kind}",
                    observed_at=str(last.get("datetime") or last.get("createdAt") or "")
                    or None,
                    raw_ref=f"project:{project_name}:events",
                )
            )
    except LiaraClientError as exc:
        gaps.append(
            EvidenceGap(
                source="events",
                reason=exc.code,
                impact="Events unavailable.",
            )
        )

    # CPU / memory — missing ≠ empty success
    for source, getter in (
        ("metrics_cpu", client.get_cpu_metrics),
        ("metrics_memory", client.get_memory_metrics),
    ):
        try:
            metrics = getter(project_name)
            if not _metrics_present(metrics):
                gaps.append(
                    EvidenceGap(
                        source=source,
                        reason="missing_or_empty",
                        impact="Cannot confirm resource pressure; mark gap (L-AC14).",
                    )
                )
            else:
                facts.append(
                    EvidenceFact(
                        id=_fid(),
                        source=source,  # type: ignore[arg-type]
                        summary=f"{source} series present",
                        observed_at=_utcnow_iso(),
                        raw_ref=f"project:{project_name}:{source}",
                    )
                )
        except LiaraClientError as exc:
            gaps.append(
                EvidenceGap(
                    source=source,
                    reason=exc.code,
                    impact="Metrics unavailable; do not invent utilization %.",
                )
            )

    complete = len(gaps) == 0 and len(facts) > 0
    version_body = {
        "project_name": project_name,
        "symptom": symptom,
        "facts": [f.model_dump() for f in facts],
        "gaps": [g.model_dump() for g in gaps],
        "sanitized": sanitized[:10],
        "injection_stripped_count": injection_count,
    }
    return EvidencePack(
        version=_content_version(version_body),
        project_name=project_name,
        symptom=symptom,
        window_note=window_note,
        collected_at=_utcnow_iso(),
        facts=facts,
        gaps=gaps,
        sanitized_log_excerpts=sanitized,
        injection_stripped_count=injection_count,
        complete=complete,
    )


def diagnose_from_evidence(pack: EvidencePack) -> Diagnosis:
    """Deterministic structured diagnosis — facts vs hypotheses, no confidence %."""
    hypotheses: list[Hypothesis] = []
    status_facts = [f for f in pack.facts if f.source == "status"]
    log_facts = [f for f in pack.facts if f.source == "logs"]
    metric_facts = [
        f for f in pack.facts if f.source in ("metrics_cpu", "metrics_memory")
    ]
    metric_gaps = [
        g for g in pack.gaps if g.source in ("metrics_cpu", "metrics_memory")
    ]

    rank = 1
    # OOM / killed in sanitized logs → memory hypothesis if metrics gap or present
    oom_support = [
        f.id
        for f in log_facts
        if re.search(r"(?i)\b(oom|killed|out of memory)\b", f.summary)
    ]
    if oom_support:
        contradict: list[str] = []
        # Healthy status mildly contradicts crash loop — still keep hypothesis
        for sf in status_facts:
            if re.search(r"(?i)RUNNING|READY|ACTIVE", sf.summary):
                contradict.append(sf.id)
        hypotheses.append(
            Hypothesis(
                id=f"h{rank}",
                rank=rank,
                statement="Process may have been OOM-killed or memory-constrained.",
                supporting_fact_ids=oom_support,
                contradicting_fact_ids=contradict,
            )
        )
        rank += 1

    error_support = [
        f.id
        for f in log_facts
        if re.search(r"(?i)\b(error|exception|fatal)\b", f.summary)
        and f.id not in oom_support
    ]
    if error_support:
        hypotheses.append(
            Hypothesis(
                id=f"h{rank}",
                rank=rank,
                statement="Runtime error visible in recent logs.",
                supporting_fact_ids=error_support,
                contradicting_fact_ids=[],
            )
        )
        rank += 1

    # Not running
    for sf in status_facts:
        if re.search(r"(?i)STOPPED|FAILED|ERROR|CRASH", sf.summary) or (
            "isDeployed=False" in sf.summary
        ):
            hypotheses.append(
                Hypothesis(
                    id=f"h{rank}",
                    rank=rank,
                    statement="App not in a healthy running state.",
                    supporting_fact_ids=[sf.id],
                    contradicting_fact_ids=[],
                )
            )
            rank += 1
            break

    # Resource pressure only if metrics present — never invent from gaps
    if metric_facts and not metric_gaps:
        hypotheses.append(
            Hypothesis(
                id=f"h{rank}",
                rank=rank,
                statement="Resource metrics available; check for sustained high utilization.",
                supporting_fact_ids=[f.id for f in metric_facts],
                contradicting_fact_ids=[],
            )
        )
        rank += 1

    insufficient = bool(pack.gaps) and not hypotheses
    if pack.gaps and not pack.complete:
        # Prefer declaring insufficient over fake root cause when only gaps
        if not hypotheses:
            insufficient = True

    next_q = None
    if metric_gaps:
        next_q = "Collect CPU/memory metrics or confirm plan supports reporting."
    elif not log_facts and any(g.source == "logs" for g in pack.gaps):
        next_q = "Retry log fetch or widen time window; build logs may be unavailable."
    elif hypotheses:
        next_q = "Choose a direct fix targeting the top hypothesis, or gather discriminating evidence."

    summary_parts = [
        f"{len(pack.facts)} facts",
        f"{len(hypotheses)} hypotheses",
        f"{len(pack.gaps)} gaps",
    ]
    if pack.injection_stripped_count:
        summary_parts.append(
            f"{pack.injection_stripped_count} log injection fragments ignored"
        )

    body = {
        "evidence_version": pack.version,
        "hypotheses": [h.model_dump() for h in hypotheses],
        "gaps": [g.model_dump() for g in pack.gaps],
        "insufficient": insufficient,
    }
    return Diagnosis(
        version=_content_version(body),
        evidence_version=pack.version,
        created_at=_utcnow_iso(),
        facts=list(pack.facts),
        hypotheses=hypotheses,
        data_gaps=list(pack.gaps),
        summary="; ".join(summary_parts),
        next_read_or_question=next_q,
        insufficient_evidence=insufficient,
    )


def build_fix_options(
    diagnosis: Diagnosis,
    *,
    project_name: str,
    registry_status: dict[str, str] | None = None,
    plan_id_for_resize: str | None = None,
) -> FixOptionsPayload:
    """Propose allowlisted direct fixes; respect disabled update_envs."""
    registry_status = registry_status or {}
    options: list[FixOption] = []
    open_needs: list[str] = []

    def _tool_enabled(tool_id: str, capability_id: str) -> tuple[bool, str | None]:
        if tool_id == "update_envs":
            return False, ENV_OPEN_NEED
        if tool_id not in ALLOWLISTED_WRITE_TOOLS and tool_id not in GATED_FIX_TOOLS:
            return False, f"tool_not_allowlisted:{tool_id}"
        if tool_id in OPS_WRITE_TOOLS or tool_id in DIRECT_FIX_TOOLS:
            status = registry_status.get(capability_id) or registry_status.get(tool_id)
            # Allow propose when documented/tested/enabled; execute still needs approval.
            if status == "disabled":
                return False, f"registry_disabled:{capability_id}"
            # Prefer tested/enabled for "enabled" flag on UI
            return status in ("tested", "enabled", "documented", None), (
                None
                if status in ("tested", "enabled", "documented", None)
                else f"registry_status:{status}"
            )
        return False, f"not_direct_fix:{tool_id}"

    # Restart — common first option for crash/OOM/error
    ok, reason = _tool_enabled("restart", "restart_resize")
    options.append(
        FixOption(
            id="fix-restart",
            tool_id="restart",
            label="Restart app",
            rationale="Clears transient process failure; verify with same health method after.",
            enabled=ok,
            disabled_reason=reason,
            verification_method="get_project_health",
            params={"project_name": project_name},
        )
    )

    # Resize — only when memory/OOM hypothesis ranked high
    top = diagnosis.hypotheses[0] if diagnosis.hypotheses else None
    wants_resize = bool(
        top
        and re.search(r"(?i)oom|memory|resource", top.statement)
        and plan_id_for_resize
    )
    ok_r, reason_r = _tool_enabled("resize", "restart_resize")
    if wants_resize:
        options.append(
            FixOption(
                id="fix-resize",
                tool_id="resize",
                label="Resize plan",
                rationale="Top hypothesis suggests resource pressure; cost unknown until priced.",
                enabled=ok_r and bool(plan_id_for_resize),
                disabled_reason=reason_r
                if ok_r
                else (reason_r or "plan_id_required"),
                verification_method="get_project_health",
                params={
                    "project_name": project_name,
                    "planID": plan_id_for_resize,
                },
            )
        )
    else:
        options.append(
            FixOption(
                id="fix-resize",
                tool_id="resize",
                label="Resize plan",
                rationale="Available when memory/resource hypothesis leads and planID known.",
                enabled=False,
                disabled_reason="not_indicated_or_missing_plan_id",
                verification_method="get_project_health",
                params={"project_name": project_name},
            )
        )

    # Env — always listed as disabled until L-D03
    options.append(
        FixOption(
            id="fix-env",
            tool_id="update_envs",
            label="Update environment variables",
            rationale="Blocked until merge/replace contract proven (L-D03).",
            enabled=False,
            disabled_reason=ENV_OPEN_NEED,
            verification_method="get_project_health",
            params={"project_name": project_name},
        )
    )
    open_needs.append(ENV_OPEN_NEED)

    # Dependency reconnect / provision — phase 4; gated by create_database registry
    from app.services.dependencies import (
        CREATE_DATABASE_CAP,
        DEP_OPEN_NEED_CREATE,
        build_dependency_reconnect_option,
    )

    dep_opt, dep_needs = build_dependency_reconnect_option(
        project_name=project_name,
        registry_status={
            CREATE_DATABASE_CAP: registry_status.get(CREATE_DATABASE_CAP, "disabled"),
        },
    )
    options.append(FixOption.model_validate(dep_opt))
    open_needs.extend(dep_needs)
    if not dep_opt.get("enabled"):
        open_needs.append(DEP_OPEN_NEED_CREATE)

    if diagnosis.insufficient_evidence:
        open_needs.append("insufficient_evidence_for_fix")

    return FixOptionsPayload(
        diagnosis_version=diagnosis.version,
        evidence_version=diagnosis.evidence_version,
        options=options,
        open_needs=sorted(set(open_needs)),
    )


def fix_option_to_ops_cfg(option: FixOption) -> dict[str, Any] | None:
    """Map an enabled fix option to create_plan(ops=...) intent."""
    if not option.enabled:
        return None
    if option.tool_id == "restart":
        return {
            "kind": "restart",
            "project_name": option.params.get("project_name"),
            "reason": "phase3_direct_fix",
        }
    if option.tool_id == "resize":
        return {
            "kind": "resize",
            "project_name": option.params.get("project_name"),
            "plan_id": option.params.get("planID") or option.params.get("plan_id"),
        }
    return None


def verify_fix_same_method(
    client: LiaraClient | None,
    *,
    project_name: str,
    method: str,
    before: dict[str, Any] | None = None,
) -> FixVerification:
    """Before/after with same method; never schedules autonomous next write."""
    before_snap = dict(before or {})
    if method == "get_project_health":
        if not before_snap:
            before_snap = post_action_health(client, project_name=project_name)
        after_snap = post_action_health(client, project_name=project_name)
    else:
        return FixVerification(
            method=method,
            before=before_snap,
            after={},
            effective=None,
            open_need=OPEN_NEED_INSUFFICIENT_AFTER,
            autonomous_next_write=False,
        )

    after_healthy = after_snap.get("healthy")
    before_healthy = before_snap.get("healthy")

    if after_healthy is None:
        return FixVerification(
            method=method,
            before=before_snap,
            after=after_snap,
            effective=None,
            open_need=OPEN_NEED_INSUFFICIENT_AFTER,
            autonomous_next_write=False,
        )

    improved = bool(after_healthy) and not bool(before_healthy)
    still_bad = not bool(after_healthy)
    if still_bad or (before_healthy and after_healthy and before_snap == after_snap):
        # Ineffective or unchanged-bad → open need, no auto retry
        return FixVerification(
            method=method,
            before=before_snap,
            after=after_snap,
            effective=False if still_bad else improved,
            open_need=OPEN_NEED_INEFFECTIVE if still_bad else None,
            autonomous_next_write=False,
        )

    return FixVerification(
        method=method,
        before=before_snap,
        after=after_snap,
        effective=True if improved or after_healthy else False,
        open_need=None if after_healthy else OPEN_NEED_INEFFECTIVE,
        autonomous_next_write=False,
    )


def refuse_autonomous_next_write(
    verification: FixVerification,
    *,
    write_guard_call_count_before: int,
    write_guard_call_count_after: int,
) -> dict[str, Any]:
    """L-AC17: after ineffective fix, assert zero additional writes."""
    delta = write_guard_call_count_after - write_guard_call_count_before
    return {
        "autonomous_next_write": False,
        "write_delta": delta,
        "open_need": verification.open_need,
        "effective": verification.effective,
        "policy": "no_autonomous_fix_loop",
        "ok": delta == 0 and verification.autonomous_next_write is False,
    }

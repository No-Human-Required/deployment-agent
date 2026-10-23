"""Phase-6 maintain: monitors, incidents, recovery baselines, audit list.

Hard rules (L-R15 / L-AC26 / L-AC40 / L-AC41):
- Enabling a monitor does NOT authorize restart, resize, or republish.
- Incident alerts never set write_authorized.
- Recovery republish / restart requires a fresh Approval (separate from monitor).
- Stale monitor data (missed checks) is never treated as live healthy green.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.maintain import Incident, Monitor, RecoveryBaseline
from app.schemas.orchestration import (
    IncidentCardPayload,
    MonitorStatusPayload,
    PlanStep,
    PlanVersion,
    RecoveryPlanPayload,
)

# After this many consecutive missed checks, last ok is stale (PRD §10).
STALE_AFTER_MISSES = 2

# Secret-ish keys stripped from audit / baseline snapshots.
_SECRET_KEY_RE = re.compile(
    r"(token|secret|password|api[_-]?key|authorization|credential)",
    re.IGNORECASE,
)

CheckResult = dict[str, Any]
PeriodicCheckFn = Callable[[Monitor], CheckResult]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sanitize_for_audit(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Drop secret-like keys/values from audit payloads (never echo credentials)."""
    if not payload:
        return {}
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if _SECRET_KEY_RE.search(str(key)):
            out[key] = "[redacted]"
            continue
        if isinstance(value, dict):
            out[key] = sanitize_for_audit(value)
        elif isinstance(value, str) and len(value) > 8 and _looks_like_secret(value):
            out[key] = "[redacted]"
        else:
            out[key] = value
    return out


def _looks_like_secret(value: str) -> bool:
    # Heuristic: long opaque tokens; never claim this catches all secrets.
    if value.startswith("Bearer "):
        return True
    if value.count(".") >= 2 and len(value) > 40:  # JWT-ish
        return True
    return False


def default_periodic_check(monitor: Monitor) -> CheckResult:
    """Callable stub for periodic health — no provider HTTP.

    Returns synthetic ok when enabled; callers inject real checks in tests/prod.
    """
    _ = monitor
    return {
        "ok": True,
        "status": "ok",
        "message": "stub_check_ok",
        "data_received": True,
    }


def monitor_to_status(monitor: Monitor) -> MonitorStatusPayload:
    stale = (
        monitor.consecutive_misses >= STALE_AFTER_MISSES
        or monitor.last_status == "stale"
    )
    # Previous green is never "live healthy" when stale.
    healthy_live = (
        monitor.enabled
        and monitor.last_status == "ok"
        and not stale
        and monitor.last_data_at is not None
    )
    return MonitorStatusPayload(
        monitor_id=str(monitor.id),
        target=monitor.target,
        enabled=monitor.enabled,
        interval_seconds=monitor.interval_seconds,
        last_status=monitor.last_status,
        last_checked_at=(
            monitor.last_checked_at.isoformat() if monitor.last_checked_at else None
        ),
        last_data_at=(
            monitor.last_data_at.isoformat() if monitor.last_data_at else None
        ),
        consecutive_misses=monitor.consecutive_misses,
        stale=stale,
        healthy_live=healthy_live,
        grants_write_permission=False,  # always false — enable ≠ write
        notification_allowed=monitor.notification_allowed,
        criteria=dict(monitor.criteria or {}),
    )


def incident_to_card(incident: Incident) -> IncidentCardPayload:
    return IncidentCardPayload(
        incident_id=str(incident.id),
        monitor_id=str(incident.monitor_id) if incident.monitor_id else None,
        case_id=str(incident.case_id) if incident.case_id else None,
        status=incident.status,
        title=incident.title,
        alert_count=incident.alert_count,
        dedupe_key=incident.dedupe_key,
        write_authorized=False,  # alert ≠ permission
        opened_at=incident.opened_at.isoformat() if incident.opened_at else None,
        resolved_at=(
            incident.resolved_at.isoformat() if incident.resolved_at else None
        ),
        evidence=sanitize_for_audit(dict(incident.evidence or {})),
        resolve_evidence=incident.resolve_evidence,
    )


class MaintainService:
    def __init__(
        self,
        session: Session,
        *,
        periodic_check: PeriodicCheckFn | None = None,
    ) -> None:
        self._session = session
        self._periodic_check = periodic_check or default_periodic_check

    # --- Monitor ---------------------------------------------------------------

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
    ) -> Monitor:
        target = target.strip()
        if not target:
            raise ValueError("monitor target required")
        if interval_seconds < 10:
            raise ValueError("interval_seconds must be >= 10")

        monitor: Monitor | None = None
        if monitor_id is not None:
            monitor = self._session.get(Monitor, monitor_id)
            if monitor is None or monitor.workspace_id != workspace_id:
                raise LookupError("monitor not found")
        else:
            monitor = self._session.scalar(
                select(Monitor).where(
                    Monitor.workspace_id == workspace_id,
                    Monitor.target == target,
                    Monitor.case_id == case_id,
                )
            )

        if monitor is None:
            monitor = Monitor(
                workspace_id=workspace_id,
                case_id=case_id,
                target=target,
                interval_seconds=interval_seconds,
                criteria=criteria,
                notification_allowed=notification_allowed,
                enabled=True,
                grants_write_permission=False,
            )
            self._session.add(monitor)
        else:
            monitor.enabled = True
            monitor.interval_seconds = interval_seconds
            if criteria is not None:
                monitor.criteria = criteria
            monitor.notification_allowed = notification_allowed
            monitor.grants_write_permission = False

        self._session.flush()
        self._audit(
            workspace_id,
            case_id or monitor.case_id,
            "monitor_enabled",
            {
                "monitor_id": str(monitor.id),
                "target": target,
                "grants_write_permission": False,
                "interval_seconds": interval_seconds,
            },
        )
        return monitor

    def disable_monitor(
        self, *, workspace_id: uuid.UUID, monitor_id: uuid.UUID
    ) -> Monitor:
        monitor = self._session.get(Monitor, monitor_id)
        if monitor is None or monitor.workspace_id != workspace_id:
            raise LookupError("monitor not found")
        monitor.enabled = False
        self._session.flush()
        self._audit(
            workspace_id,
            monitor.case_id,
            "monitor_disabled",
            {"monitor_id": str(monitor.id), "target": monitor.target},
        )
        return monitor

    def get_monitor(
        self, *, workspace_id: uuid.UUID, monitor_id: uuid.UUID
    ) -> Monitor:
        monitor = self._session.get(Monitor, monitor_id)
        if monitor is None or monitor.workspace_id != workspace_id:
            raise LookupError("monitor not found")
        return monitor

    def list_monitors(self, *, workspace_id: uuid.UUID) -> list[Monitor]:
        return list(
            self._session.scalars(
                select(Monitor)
                .where(Monitor.workspace_id == workspace_id)
                .order_by(Monitor.created_at.desc())
            ).all()
        )

    def run_periodic_check(
        self,
        *,
        workspace_id: uuid.UUID,
        monitor_id: uuid.UUID,
        now: datetime | None = None,
    ) -> tuple[Monitor, Incident | None]:
        """Invoke check stub; open/dedupe incident on alert; mark stale on misses."""
        monitor = self.get_monitor(workspace_id=workspace_id, monitor_id=monitor_id)
        if not monitor.enabled:
            raise ValueError("monitor is disabled")

        clock = now or _utcnow()
        result = self._periodic_check(monitor)
        monitor.last_checked_at = clock

        data_received = bool(result.get("data_received", True))
        ok = bool(result.get("ok", False)) and data_received
        incident: Incident | None = None

        if not data_received or result.get("status") == "error":
            monitor.consecutive_misses += 1
            if monitor.consecutive_misses >= STALE_AFTER_MISSES:
                monitor.last_status = "stale"
            else:
                monitor.last_status = "error"
            # Stale ≠ app failure; do not auto-open write-authorized incident.
            self._session.flush()
            self._audit(
                workspace_id,
                monitor.case_id,
                "monitor_check",
                {
                    "monitor_id": str(monitor.id),
                    "status": monitor.last_status,
                    "consecutive_misses": monitor.consecutive_misses,
                    "stale": monitor.consecutive_misses >= STALE_AFTER_MISSES,
                },
            )
            return monitor, None

        if ok:
            monitor.consecutive_misses = 0
            monitor.last_status = "ok"
            monitor.last_data_at = clock
            self._session.flush()
            self._audit(
                workspace_id,
                monitor.case_id,
                "monitor_check",
                {
                    "monitor_id": str(monitor.id),
                    "status": "ok",
                    "consecutive_misses": 0,
                },
            )
            return monitor, None

        # Alert path — open or bump incident; never authorize write.
        monitor.consecutive_misses = 0
        monitor.last_status = "alert"
        monitor.last_data_at = clock
        dedupe_key = (
            f"{monitor.target}:{result.get('symptom') or result.get('code') or 'alert'}"
        )
        incident = self.open_or_bump_incident(
            workspace_id=workspace_id,
            monitor=monitor,
            dedupe_key=dedupe_key,
            title=str(result.get("message") or f"alert on {monitor.target}"),
            evidence=sanitize_for_audit(
                {
                    "check": {k: v for k, v in result.items() if k != "raw"},
                    "target": monitor.target,
                }
            ),
        )
        self._session.flush()
        return monitor, incident

    # --- Incident --------------------------------------------------------------

    def open_or_bump_incident(
        self,
        *,
        workspace_id: uuid.UUID,
        monitor: Monitor,
        dedupe_key: str,
        title: str,
        evidence: dict[str, Any] | None = None,
    ) -> Incident:
        existing = self._session.scalar(
            select(Incident).where(
                Incident.workspace_id == workspace_id,
                Incident.dedupe_key == dedupe_key,
                Incident.status == "open",
            )
        )
        if existing is not None:
            existing.alert_count += 1
            existing.write_authorized = False
            if evidence:
                merged = dict(existing.evidence or {})
                merged["latest"] = evidence
                existing.evidence = sanitize_for_audit(merged)
            self._session.flush()
            self._audit(
                workspace_id,
                monitor.case_id,
                "monitor_incident_bumped",
                {
                    "incident_id": str(existing.id),
                    "alert_count": existing.alert_count,
                    "write_authorized": False,
                },
            )
            return existing

        incident = Incident(
            workspace_id=workspace_id,
            monitor_id=monitor.id,
            case_id=monitor.case_id,
            dedupe_key=dedupe_key,
            status="open",
            title=title[:512],
            alert_count=1,
            evidence=sanitize_for_audit(evidence or {}),
            write_authorized=False,
        )
        self._session.add(incident)
        self._session.flush()
        self._audit(
            workspace_id,
            monitor.case_id,
            "monitor_incident_opened",
            {
                "incident_id": str(incident.id),
                "dedupe_key": dedupe_key,
                "write_authorized": False,
            },
        )
        return incident

    def resolve_incident(
        self,
        *,
        workspace_id: uuid.UUID,
        incident_id: uuid.UUID,
        evidence: str,
    ) -> Incident:
        incident = self._session.get(Incident, incident_id)
        if incident is None or incident.workspace_id != workspace_id:
            raise LookupError("incident not found")
        if not evidence or not evidence.strip():
            raise ValueError("resolve requires evidence")
        incident.status = "resolved"
        incident.resolved_at = _utcnow()
        incident.resolve_evidence = evidence.strip()[:4000]
        incident.write_authorized = False
        self._session.flush()
        self._audit(
            workspace_id,
            incident.case_id,
            "monitor_incident_resolved",
            {
                "incident_id": str(incident.id),
                "has_evidence": True,
                "write_authorized": False,
            },
        )
        return incident

    def list_incidents(
        self, *, workspace_id: uuid.UUID, status: str | None = None
    ) -> list[Incident]:
        stmt = select(Incident).where(Incident.workspace_id == workspace_id)
        if status:
            stmt = stmt.where(Incident.status == status)
        return list(
            self._session.scalars(stmt.order_by(Incident.opened_at.desc())).all()
        )

    # --- Recovery baseline -----------------------------------------------------

    def capture_baseline(
        self,
        *,
        workspace_id: uuid.UUID,
        project_name: str,
        case_id: uuid.UUID | None = None,
        snapshot: dict[str, Any] | None = None,
        source_operation_id: uuid.UUID | None = None,
    ) -> RecoveryBaseline:
        """Snapshot before sensitive writes — secret values stripped."""
        project_name = project_name.strip()
        if not project_name:
            raise ValueError("project_name required")
        clean = sanitize_for_audit(
            snapshot
            or {
                "project_name": project_name,
                "note": "pre_write_baseline",
                "captured_at": _utcnow().isoformat(),
            }
        )
        # Prefer secret refs over values if present.
        if "env" in clean and isinstance(clean["env"], dict):
            clean["env_keys"] = sorted(clean["env"].keys())
            clean.pop("env", None)
        baseline = RecoveryBaseline(
            workspace_id=workspace_id,
            case_id=case_id,
            project_name=project_name,
            snapshot=clean,
            source_operation_id=source_operation_id,
        )
        self._session.add(baseline)
        self._session.flush()
        self._audit(
            workspace_id,
            case_id,
            "recovery_baseline_captured",
            {
                "baseline_id": str(baseline.id),
                "project_name": project_name,
                "snapshot_keys": sorted(clean.keys()),
            },
        )
        return baseline

    def latest_baseline(
        self, *, workspace_id: uuid.UUID, project_name: str
    ) -> RecoveryBaseline | None:
        return self._session.scalar(
            select(RecoveryBaseline)
            .where(
                RecoveryBaseline.workspace_id == workspace_id,
                RecoveryBaseline.project_name == project_name,
            )
            .order_by(RecoveryBaseline.created_at.desc())
            .limit(1)
        )

    def build_recovery_plan(
        self,
        *,
        workspace_id: uuid.UUID,
        project_name: str,
        case_id: uuid.UUID | None = None,
        action: str = "restart",
        baseline_id: uuid.UUID | None = None,
    ) -> tuple[PlanVersion, RecoveryPlanPayload, RecoveryBaseline]:
        """Propose recovery steps from baseline — execution still needs approval."""
        if action not in ("restart", "republish"):
            raise ValueError("action must be restart or republish")

        baseline: RecoveryBaseline | None
        if baseline_id is not None:
            baseline = self._session.get(RecoveryBaseline, baseline_id)
            if baseline is None or baseline.workspace_id != workspace_id:
                raise LookupError("baseline not found")
        else:
            baseline = self.latest_baseline(
                workspace_id=workspace_id, project_name=project_name
            )
        if baseline is None:
            raise LookupError("no recovery baseline for project")

        if action == "restart":
            steps = [
                PlanStep(
                    id="recovery-restart",
                    action="restart_from_baseline",
                    tool_id="restart",
                    effects=["restart_project"],
                    cost_known=True,
                    cost_estimate="0",
                    params={"project_name": project_name},
                )
            ]
            summary = f"Restart {project_name} from recovery baseline"
        else:
            # Republish path — sources+releases; still gated by approval + WriteGuard.
            snap = baseline.snapshot or {}
            port = int(snap.get("port") or 3000)
            platform = str(snap.get("platform") or "node")
            archive = str(snap.get("archive_path") or "")
            steps = [
                PlanStep(
                    id="recovery-sources",
                    action="republish_source",
                    tool_id="sources",
                    effects=["upload_source"],
                    cost_known=False,
                    params={
                        "project_name": project_name,
                        "archive_path": archive or "/tmp/recovery.tar.gz",
                    },
                ),
                PlanStep(
                    id="recovery-release",
                    action="republish_release",
                    tool_id="releases",
                    effects=["create_release"],
                    cost_known=False,
                    params={
                        "project_name": project_name,
                        "port": port,
                        "platform": platform,
                        "sourceID": "from_prior_step",
                    },
                ),
            ]
            summary = f"Republish {project_name} from recovery baseline"

        plan = PlanVersion(
            version=1,
            steps=steps,
            effects=[s.action for s in steps],
            cost_known=action == "restart",
            cost_summary="unknown" if action == "republish" else "0",
            summary=summary,
            target_platform=str((baseline.snapshot or {}).get("platform") or "node"),
        )
        view = RecoveryPlanPayload(
            baseline_id=str(baseline.id),
            project_name=project_name,
            action=action,
            requires_fresh_approval=True,
            monitor_enable_authorizes=False,
            incident_alert_authorizes=False,
            plan=plan.model_dump(mode="json"),
            snapshot_keys=sorted((baseline.snapshot or {}).keys()),
            summary=summary,
            open_needs=(
                ["archive_path_required_for_republish"]
                if action == "republish"
                and not (baseline.snapshot or {}).get("archive_path")
                else []
            ),
        )
        _ = case_id  # reserved for case linkage by orchestrator
        return plan, view, baseline

    # --- Audit list ------------------------------------------------------------

    def list_audit_events(
        self,
        *,
        workspace_id: uuid.UUID,
        case_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.workspace_id == workspace_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(min(max(limit, 1), 200))
        )
        if case_id is not None:
            stmt = stmt.where(AuditEvent.case_id == case_id)
        rows = list(self._session.scalars(stmt).all())
        return [
            {
                "id": str(ev.id),
                "event_type": ev.event_type,
                "actor": ev.actor,
                "case_id": str(ev.case_id) if ev.case_id else None,
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
                "payload": sanitize_for_audit(dict(ev.payload or {})),
            }
            for ev in rows
        ]

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
                event_type=f"maintain.{event_type}",
                payload=sanitize_for_audit(payload),
                actor="maintain",
            )
        )
        # Tests use autoflush=False; ensure list_audit sees pending rows.
        self._session.flush()


DOCUMENTED_ADAPTER_TOOL_IDS = frozenset(
    {
        "adapter_django",
        "adapter_laravel",
        "adapter_dotnet",
        "adapter_static",
        "adapter_docker",
    }
)


def ensure_documented_adapters(registry: Any) -> list[str]:
    """Seed catalog rows for remaining adapters; assert they stay documented."""
    from app.services.registry import CapabilityNotFound

    registry.seed()
    found: list[str] = []
    for tool_id in sorted(DOCUMENTED_ADAPTER_TOOL_IDS):
        try:
            cap = registry.get(tool_id)
        except CapabilityNotFound:
            continue
        if cap.status != "documented":
            # Honesty: never silently claim enabled/tested without proof.
            continue
        found.append(tool_id)
    return found

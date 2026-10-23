"""Capability registry — seed catalog and controlled status transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.capability import Capability

ALLOWED_STATUSES = frozenset({"documented", "tested", "enabled", "disabled"})

# documented → tested → enabled; any non-permanent can move to disabled;
# disabled → documented (re-open), except permanently_disabled rows.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "documented": frozenset({"tested", "disabled"}),
    "tested": frozenset({"enabled", "disabled", "documented"}),
    "enabled": frozenset({"disabled", "tested"}),
    "disabled": frozenset({"documented"}),
}


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    tool_id: str
    service: str
    status: str
    permanently_disabled: bool = False
    metadata: dict[str, Any] | None = None
    ac_refs: list[str] | None = None
    notes: str | None = None


# Impl plan §5 — starting statuses; native rollback + Irnic stay disabled.
SEED_CATALOG: tuple[CatalogEntry, ...] = (
    CatalogEntry(
        tool_id="list_get_projects",
        service="paas",
        status="documented",
        ac_refs=["L-AC01"],
        notes="list/get projects — read path; promote to tested in Phase 0",
    ),
    CatalogEntry(
        tool_id="create_project",
        service="paas",
        status="documented",
        ac_refs=["L-AC22"],
        notes="create project — duplicate name + timeout checks",
    ),
    CatalogEntry(
        tool_id="sources_releases",
        service="paas",
        status="documented",
        ac_refs=["L-AC08", "L-AC11", "L-AC12", "L-AC32"],
        notes="sources + releases",
    ),
    CatalogEntry(
        tool_id="update_envs",
        service="paas",
        status="disabled",
        ac_refs=["L-D03", "L-AC23", "L-AC36"],
        notes=(
            "update-envs — OpenAPI has no merge/replace mode; "
            "disabled until L-D03 proven (prefer disabled over fake merge)"
        ),
    ),
    CatalogEntry(
        tool_id="evidence_reads",
        service="paas",
        status="documented",
        ac_refs=["L-AC13", "L-AC14"],
        notes="logs / events / cpu / memory — sanitize before LLM; gaps ≠ empty success",
    ),
    CatalogEntry(
        tool_id="restart_resize",
        service="paas",
        status="documented",
        notes="restart / resize — health after action; cost unknown for resize",
    ),
    CatalogEntry(
        tool_id="domains_ssl",
        service="paas",
        status="documented",
        ac_refs=["L-AC24"],
        notes="domains + ssl — SSL request accepted ≠ cert valid",
    ),
    CatalogEntry(
        tool_id="dns_records",
        service="dns",
        status="documented",
        ac_refs=["L-D09"],
        notes="dns records — only zones under account; else handoff",
    ),
    CatalogEntry(
        tool_id="create_database",
        service="dbaas",
        status="disabled",
        ac_refs=["L-D05", "L-AC43"],
        notes=(
            "POST /v1/databases — API documented but live create unproven (L-D05). "
            "Discovery + open-need always on; mocked create behind approval when enabled. "
            "Do not claim complete success while required DB missing."
        ),
    ),
    CatalogEntry(
        tool_id="create_disk",
        service="paas",
        status="disabled",
        ac_refs=["L-D05", "L-AC44"],
        notes=(
            "POST /v1/projects/{name}/disks — documented; live create unproven (L-D05). "
            "Incomplete disks stay on Case.pending_resources; enable only after proof."
        ),
    ),
    CatalogEntry(
        tool_id="sandbox_run",
        service="sandbox",
        status="documented",
        ac_refs=["L-AC37", "L-AC39", "L-AC46"],
        notes=(
            "Constrained sandbox: temp copy + allowlisted test cmd + secret scrub. "
            "Network isolation often unavailable on bare subprocess — fail-closed for "
            "ready_for_release; approve_patch_record ≠ approve_release. Promote to "
            "tested under mock; never auto-release on red tests."
        ),
    ),
    CatalogEntry(
        tool_id="native_rollback",
        service="paas",
        status="disabled",
        permanently_disabled=True,
        notes="not in public API — always disabled; use re-release path",
    ),
    CatalogEntry(
        tool_id="cancel_in_flight_write",
        service="paas",
        status="documented",
        notes="cancel in-flight write — unclear API; stop next step only",
    ),
    CatalogEntry(
        tool_id="irnic_payment",
        service="dns",
        status="disabled",
        permanently_disabled=True,
        notes="Irnic / payment automation — out of scope; manual handoff",
    ),
    # Remaining platform adapters — documented only until independently proven (PRD §7).
    CatalogEntry(
        tool_id="adapter_django",
        service="adapter",
        status="documented",
        ac_refs=["L-AC27", "L-AC42"],
        notes="Django readiness/deploy — documented only; not enabled",
    ),
    CatalogEntry(
        tool_id="adapter_laravel",
        service="adapter",
        status="documented",
        ac_refs=["L-AC27", "L-AC42"],
        notes="Laravel readiness/deploy — documented only; not enabled",
    ),
    CatalogEntry(
        tool_id="adapter_dotnet",
        service="adapter",
        status="documented",
        ac_refs=["L-AC27", "L-AC42"],
        notes=".NET readiness/deploy — documented only; not enabled",
    ),
    CatalogEntry(
        tool_id="adapter_static",
        service="adapter",
        status="documented",
        ac_refs=["L-AC27", "L-AC42"],
        notes="React/Vue static — documented only; do not misclassify SSR as static",
    ),
    CatalogEntry(
        tool_id="adapter_docker",
        service="adapter",
        status="documented",
        ac_refs=["L-AC27", "L-AC42"],
        notes="Docker build/deploy — documented only; compatibility not assumed",
    ),
)


class InvalidCapabilityTransition(ValueError):
    pass


class CapabilityNotFound(LookupError):
    pass


class CapabilityRegistry:
    def __init__(self, session: Session) -> None:
        self._session = session

    def seed(self, *, force: bool = False) -> int:
        """Insert catalog rows that are missing. Returns number inserted."""
        inserted = 0
        for entry in SEED_CATALOG:
            existing = self._session.scalar(
                select(Capability).where(Capability.tool_id == entry.tool_id)
            )
            if existing is not None:
                if force:
                    existing.service = entry.service
                    existing.status = entry.status
                    existing.permanently_disabled = entry.permanently_disabled
                    existing.metadata_json = entry.metadata
                    existing.ac_refs = entry.ac_refs
                    existing.notes = entry.notes
                continue
            self._session.add(
                Capability(
                    tool_id=entry.tool_id,
                    service=entry.service,
                    status=entry.status,
                    permanently_disabled=entry.permanently_disabled,
                    metadata_json=entry.metadata,
                    ac_refs=entry.ac_refs,
                    notes=entry.notes,
                )
            )
            inserted += 1
        self._session.flush()
        return inserted

    def list_all(self) -> list[Capability]:
        return list(
            self._session.scalars(select(Capability).order_by(Capability.tool_id)).all()
        )

    def list_by_service(self, service: str) -> list[Capability]:
        return list(
            self._session.scalars(
                select(Capability)
                .where(Capability.service == service)
                .order_by(Capability.tool_id)
            ).all()
        )

    def get(self, tool_id: str) -> Capability:
        row = self._session.scalar(
            select(Capability).where(Capability.tool_id == tool_id)
        )
        if row is None:
            raise CapabilityNotFound(tool_id)
        return row

    def set_status(self, tool_id: str, new_status: str) -> Capability:
        if new_status not in ALLOWED_STATUSES:
            raise InvalidCapabilityTransition(f"unknown status: {new_status}")
        cap = self.get(tool_id)
        if cap.permanently_disabled and new_status != "disabled":
            raise InvalidCapabilityTransition(
                f"{tool_id} is permanently disabled and cannot leave disabled"
            )
        allowed = ALLOWED_TRANSITIONS.get(cap.status, frozenset())
        if new_status not in allowed:
            raise InvalidCapabilityTransition(
                f"cannot transition {tool_id} from {cap.status!r} to {new_status!r}"
            )
        cap.status = new_status
        self._session.flush()
        return cap

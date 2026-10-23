"""Phase-4 dependencies — discover DB/Redis/disk; approval-gated create when enabled.

L-D05 honesty: ``create_database`` / ``create_disk`` stay documented/disabled until
live create is proven. Discovery + open-need always work; mocked create runs only
when registry status is ``enabled`` (tests can promote).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.case import Case
from app.schemas.orchestration import PlanStep, PlanVersion
from app.services.deploy import request_body_fingerprint
from app.services.liara_client import LiaraClient, LiaraClientError, LiaraTimeoutError
from app.services.registry import CapabilityRegistry
from app.services.secrets import SecretService
from app.services.write_guard import LiaraProviderWrite, WriteGuard, WriteNotAllowlisted

logger = logging.getLogger(__name__)

CREATE_DATABASE_CAP = "create_database"
CREATE_DISK_CAP = "create_disk"
DEP_OPEN_NEED_CREATE = "dependency_create_ld05_unproven"
DEP_OPEN_NEED_REQUIRED = "required_dependency_missing"
DEP_OPEN_NEED_INCOMPLETE = "dependency_resource_incomplete"

OP_STATE_DEPS_DONE = "deps_done"
OP_STATE_DEPS_PARTIAL = "deps_partial"
OP_STATE_DEPS_BLOCKED = "deps_blocked"
OP_STATE_HANDOFF = "handoff"
OP_STATE_UNKNOWN = "unknown"

DEP_WRITE_TOOLS = frozenset({"create_database", "create_disk"})

# Valid web-push VAPID pair for first boot (not production secrets).
# Placeholder strings like ``replace-with-…`` crash Nest at NotificationsService init.
_BOOTSTRAP_VAPID_PUBLIC = (
    "BJSbE6SGmtU-QI1OAmLMayp3Cg1oxr3PydvirJf2c171wwfphDO5lWsw_"
    "lswiXMxq8HmJJnjRKaHvcwUNa2tX2M"
)
_BOOTSTRAP_VAPID_PRIVATE = "MFY2VUtl5xlV8MR8iY5CUTceCtqLrldsAr1YvvPbwPc"


def _invalid_vapid_env(key: str, value: str) -> bool:
    """True when a stored VAPID value would crash ``web-push`` at boot."""
    raw = (value or "").strip()
    if not raw:
        return True
    lowered = raw.lower()
    if any(
        marker in lowered
        for marker in ("replace", "change-me", "example", "todo", "xxx")
    ):
        return True
    # Uncompressed public key is ~87 chars; private ~43 (URL-safe base64).
    if key == "VAPID_PUBLIC_KEY" and len(raw) < 80:
        return True
    if key == "VAPID_PRIVATE_KEY" and len(raw) < 40:
        return True
    return False


_PLACEHOLDER_ENV_MARKERS = (
    "replace",
    "change-me",
    "example.com",
    "example@",
    "todo",
    "xxx",
    "your-",
    "placeholder",
)

# Never copy these from a local .env onto Liara (private DBaaS / platform owns them).
_LOCAL_ENV_SKIP = frozenset(
    {
        "DATABASE_URL",
        "PORT",
        "NODE_ENV",
        "STORAGE_PATH",
    }
)


def _is_placeholder_env_value(value: str) -> bool:
    raw = (value or "").strip()
    if not raw:
        return True
    lowered = raw.lower()
    return any(marker in lowered for marker in _PLACEHOLDER_ENV_MARKERS)


def _load_local_dotenv_map(app_root: str | Path | None) -> dict[str, str]:
    """Read non-secret-logged ``.env`` key/values from the deploy app (or parents)."""
    if not app_root:
        return {}
    root = Path(app_root).expanduser().resolve()
    candidates = [
        root / ".env",
        root.parent / ".env",
        root.parent.parent / ".env",
    ]
    out: dict[str, str] = {}
    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, _, val = raw.partition("=")
            key = key.strip()
            if not key or key in _LOCAL_ENV_SKIP:
                continue
            val = val.strip().strip("'").strip('"')
            if _is_placeholder_env_value(val):
                continue
            out.setdefault(key, val)
        if out:
            break
    return out


# package.json dependency name → resource kind
_PKG_SIGNALS: dict[str, str] = {
    "pg": "postgres",
    "postgres": "postgres",
    "postgresql": "postgres",
    "@neondatabase/serverless": "postgres",
    "mysql": "mysql",
    "mysql2": "mysql",
    "mariadb": "mysql",
    "redis": "redis",
    "ioredis": "redis",
    "@redis/client": "redis",
    "mongoose": "mongodb",
    "mongodb": "mongodb",
}

_ENV_KEY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)^(DATABASE_URL|POSTGRES(_URL|_URI)?|PG(HOST|DATABASE|URL))$"), "postgres"),
    (re.compile(r"(?i)^(MYSQL(_URL|_URI|_HOST)?|MARIADB(_URL)?)$"), "mysql"),
    (re.compile(r"(?i)^(REDIS(_URL|_URI|_HOST)?|CACHE_URL)$"), "redis"),
    (re.compile(r"(?i)^(MONGO(_URL|_URI)?|MONGODB_URI)$"), "mongodb"),
    (re.compile(r"(?i)^(DISK_|VOLUME_|UPLOAD_|STORAGE_PATH|PERSIST)"), "disk"),
]

_DISK_PKG = frozenset({"multer", "formidable", "busboy", "sharp", "fs-extra"})

# Default Liara DBaaS versions / plan when proposing create (live catalog).
_DEFAULT_VERSIONS: dict[str, str] = {
    "postgres": "16.14",
    "mysql": "8.0",
    "redis": "7.2",
    "mongodb": "7.0",
}
# ir-small is listed but often returns g1_plan_unavailable; small-g2 works with bundle.
_DEFAULT_PLAN_ID = "small-g2"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact_secrets_in_text(text: str) -> str:
    """Never leave passwords/URLs with credentials in logs or GenUI."""
    cleaned = re.sub(
        r"(?i)(password|passwd|pwd|secret|token)\s*[:=]\s*\S+",
        r"\1=[redacted]",
        text,
    )
    cleaned = re.sub(
        r"(?i)(postgres|mysql|mongodb|redis)://[^\s\"']+",
        r"\1://[redacted]",
        cleaned,
    )
    return cleaned


@dataclass(frozen=True, slots=True)
class DependencyFinding:
    kind: str  # postgres | mysql | redis | mongodb | disk
    code: str
    message: str
    evidence_paths: tuple[str, ...]
    required: bool = True
    severity: str = "error"  # error | warn | info

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "code": self.code,
            "message": self.message,
            "evidence_paths": list(self.evidence_paths),
            "required": self.required,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class DependencyDiscovery:
    """File-backed dependency needs — never claims provider create readiness."""

    findings: tuple[DependencyFinding, ...]
    required_kinds: tuple[str, ...]
    notes: str | None = None
    app_root: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "required_kinds": list(self.required_kinds),
            "notes": self.notes,
            "app_root": self.app_root,
            "has_required": bool(self.required_kinds),
        }


@dataclass(frozen=True, slots=True)
class DependencyPlanView:
    """GenUI ``dependency_plan`` payload — create flags honest to registry."""

    version: str
    discovery: dict[str, Any]
    proposed_creates: list[dict[str, Any]]
    create_database_enabled: bool
    create_disk_enabled: bool
    open_needs: list[str]
    handoff: dict[str, Any] | None
    pending_resources: list[dict[str, Any]]
    can_claim_complete_success: bool
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "discovery": self.discovery,
            "proposed_creates": self.proposed_creates,
            "create_database_enabled": self.create_database_enabled,
            "create_disk_enabled": self.create_disk_enabled,
            "open_needs": list(self.open_needs),
            "handoff": self.handoff,
            "pending_resources": list(self.pending_resources),
            "can_claim_complete_success": self.can_claim_complete_success,
            "summary": self.summary,
        }


@dataclass
class DepAttempt:
    step_id: str
    tool_id: str
    fingerprint: str
    status: str
    provider_ids: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    secret_ref_id: str | None = None
    at: str = field(default_factory=_utcnow_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "tool_id": self.tool_id,
            "fingerprint": self.fingerprint,
            "status": self.status,
            "provider_ids": self.provider_ids,
            "error": self.error,
            "secret_ref_id": self.secret_ref_id,
            "at": self.at,
        }


@dataclass
class DepResult:
    state: str
    attempts: list[DepAttempt]
    provider_ids: dict[str, Any]
    checkpoint: dict[str, Any]
    write_count: int
    pending_resources: list[dict[str, Any]]

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            **self.checkpoint,
            "attempts": [a.to_dict() for a in self.attempts],
            "provider_ids": self.provider_ids,
            "pending_resources": self.pending_resources,
            "mode": "phase4_dependencies",
            "updated_at": _utcnow_iso(),
        }


def discover_dependencies(app_root: str | Path) -> DependencyDiscovery:
    """Heuristic scan of manifests / env examples — every finding is file-backed.

    For monorepos, scans the workspace root plus preferred app packages
    (``apps/api``, ``apps/web``, …) so DB signals in nested packages are found.
    """
    root = Path(app_root).resolve()
    findings: list[DependencyFinding] = []
    seen: set[str] = set()

    if not root.is_dir():
        return DependencyDiscovery(
            findings=(
                DependencyFinding(
                    kind="unknown",
                    code="app_root_missing",
                    message=f"app root not found: {root}",
                    evidence_paths=(str(root),),
                    required=False,
                    severity="error",
                ),
            ),
            required_kinds=(),
            notes="invalid app root",
            app_root=str(root),
        )

    scan_roots = [root]
    for rel in (
        "apps/api",
        "apps/server",
        "apps/backend",
        "apps/web",
        "packages/api",
        "api",
        "server",
    ):
        candidate = root / rel
        if candidate.is_dir() and (candidate / "package.json").is_file():
            scan_roots.append(candidate)

    # Dedup while preserving order
    unique_roots: list[Path] = []
    for path in scan_roots:
        if path not in unique_roots:
            unique_roots.append(path)

    for scan_root in unique_roots:
        _scan_package_and_env(scan_root, findings=findings, seen=seen)

    required = tuple(
        sorted({f.kind for f in findings if f.required and f.kind != "unknown"})
    )
    return DependencyDiscovery(
        findings=tuple(findings),
        required_kinds=required,
        notes=f"scanned {', '.join(str(p) for p in unique_roots)}",
        app_root=str(root),
    )


def _scan_package_and_env(
    root: Path,
    *,
    findings: list[DependencyFinding],
    seen: set[str],
) -> None:
    pkg_path = root / "package.json"
    if pkg_path.is_file():
        try:
            package = json.loads(pkg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(
                DependencyFinding(
                    kind="unknown",
                    code="invalid_package_json",
                    message=f"package.json unreadable: {exc}",
                    evidence_paths=(str(pkg_path),),
                    required=False,
                    severity="warn",
                )
            )
            package = {}
        if isinstance(package, dict):
            deps = {
                **(package.get("dependencies") or {}),
                **(package.get("devDependencies") or {}),
            }
            for name, kind in _PKG_SIGNALS.items():
                if name in deps and kind not in seen:
                    seen.add(kind)
                    findings.append(
                        DependencyFinding(
                            kind=kind,
                            code=f"need_{kind}_from_package",
                            message=f"package.json lists {name} → needs {kind}",
                            evidence_paths=(str(pkg_path),),
                            required=True,
                        )
                    )
            disk_hits = sorted(_DISK_PKG & set(deps))
            if disk_hits and "disk" not in seen:
                seen.add("disk")
                findings.append(
                    DependencyFinding(
                        kind="disk",
                        code="need_disk_from_package",
                        message=f"upload/fs packages suggest persistent disk: {', '.join(disk_hits)}",
                        evidence_paths=(str(pkg_path),),
                        required=True,
                    )
                )

    for env_name in (".env.example", ".env.sample", ".env.template", "env.example"):
        env_path = root / env_name
        if not env_path.is_file():
            continue
        try:
            text = env_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key = stripped.split("=", 1)[0].strip()
            for pattern, kind in _ENV_KEY_PATTERNS:
                if pattern.match(key) and kind not in seen:
                    seen.add(kind)
                    findings.append(
                        DependencyFinding(
                            kind=kind,
                            code=f"need_{kind}_from_env_example",
                            message=f"{env_name} declares {key}",
                            evidence_paths=(str(env_path),),
                            required=True,
                        )
                    )

    liara_json = root / "liara.json"
    if liara_json.is_file():
        try:
            cfg = json.loads(liara_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cfg = None
        if isinstance(cfg, dict):
            disks = cfg.get("disks") or cfg.get("disk")
            if disks and "disk" not in seen:
                seen.add("disk")
                findings.append(
                    DependencyFinding(
                        kind="disk",
                        code="need_disk_from_liara_json",
                        message="liara.json declares disks",
                        evidence_paths=(str(liara_json),),
                        required=True,
                    )
                )


def registry_create_enabled(registry: CapabilityRegistry, tool_id: str) -> bool:
    try:
        cap = registry.get(tool_id)
    except Exception:
        return False
    return cap.status == "enabled"


def ensure_create_tools_honest(registry: CapabilityRegistry) -> list[str]:
    """Keep unproven create tools out of enabled; return open-need codes."""
    registry.seed()
    needs: list[str] = []
    for tool_id in (CREATE_DATABASE_CAP, CREATE_DISK_CAP):
        cap = registry.get(tool_id)
        if cap.status == "enabled":
            continue
        # Prefer staying documented/disabled — do not auto-enable.
        if cap.status not in ("documented", "disabled", "tested"):
            continue
        needs.append(DEP_OPEN_NEED_CREATE)
    return sorted(set(needs))


def build_dependency_plan_view(
    discovery: DependencyDiscovery,
    *,
    registry: CapabilityRegistry,
    pending_resources: list[dict[str, Any]] | None = None,
    project_name: str | None = None,
    hostname_prefix: str = "dep",
    plan_id: str = _DEFAULT_PLAN_ID,
) -> DependencyPlanView:
    """Build GenUI-ready plan: propose creates; gate on registry honesty."""
    registry.seed()
    db_enabled = registry_create_enabled(registry, CREATE_DATABASE_CAP)
    disk_enabled = registry_create_enabled(registry, CREATE_DISK_CAP)
    open_needs: list[str] = []
    proposed: list[dict[str, Any]] = []
    handoff: dict[str, Any] | None = None
    pending = list(pending_resources or [])

    for kind in discovery.required_kinds:
        if kind == "disk":
            entry = {
                "kind": "disk",
                "tool_id": "create_disk",
                "action": "create_disk",
                "enabled": disk_enabled,
                "params": {
                    "project_name": project_name or "app",
                    "name": "data",
                    "size": "2",
                },
            }
            if not disk_enabled:
                entry["disabled_reason"] = DEP_OPEN_NEED_CREATE
                open_needs.append(DEP_OPEN_NEED_CREATE)
            proposed.append(entry)
            continue

        # DBaaS kinds
        hostname = f"{hostname_prefix}-{kind}"[:32]
        # Liara DBaaS types: postgres (not postgresql), mysql, redis, mongodb, …
        db_type = "postgres" if kind == "postgres" else kind
        db_params: dict[str, Any] = {
            "hostname": hostname,
            "type": db_type,
            "planID": plan_id if plan_id not in ("small", "free") else _DEFAULT_PLAN_ID,
            "version": _DEFAULT_VERSIONS.get(kind, "16"),
            "publicNetwork": False,
        }
        if project_name:
            db_params["project_name"] = project_name
        entry = {
            "kind": kind,
            "tool_id": "create_database",
            "action": "create_database",
            "enabled": db_enabled,
            "params": db_params,
        }
        if not db_enabled:
            entry["disabled_reason"] = DEP_OPEN_NEED_CREATE
            open_needs.append(DEP_OPEN_NEED_CREATE)
        proposed.append(entry)

    if discovery.required_kinds and not (db_enabled or disk_enabled):
        open_needs.append(DEP_OPEN_NEED_REQUIRED)
        handoff = {
            "reason": "ld05_create_unproven",
            "message": (
                "Required DB/Redis/disk detected, but create tools are not enabled "
                "(L-D05). Create manually in Liara console or enable after live proof."
            ),
            "next_steps": [
                "Create the resource in Liara console (DBaaS / Disks).",
                "Store connection URL via Settings/SecretService (never paste into chat).",
                "Re-run discover_dependencies after attach.",
            ],
        }

    if pending:
        open_needs.append(DEP_OPEN_NEED_INCOMPLETE)

    open_needs = sorted(set(open_needs))
    can_complete = not discovery.required_kinds or (
        not open_needs
        and not pending
        and all(p.get("enabled") for p in proposed)
    )
    # Missing required deps always block "complete success" until resolved.
    if discovery.required_kinds and (
        DEP_OPEN_NEED_CREATE in open_needs
        or DEP_OPEN_NEED_REQUIRED in open_needs
        or DEP_OPEN_NEED_INCOMPLETE in open_needs
        or pending
    ):
        can_complete = False

    version = f"deps-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    summary_parts = []
    if discovery.required_kinds:
        summary_parts.append(
            "required: " + ", ".join(discovery.required_kinds)
        )
    else:
        summary_parts.append("no required dependencies detected")
    if not db_enabled:
        summary_parts.append("create_database not enabled (L-D05)")
    if not disk_enabled and "disk" in discovery.required_kinds:
        summary_parts.append("create_disk not enabled (L-D05)")

    return DependencyPlanView(
        version=version,
        discovery=discovery.to_dict(),
        proposed_creates=proposed,
        create_database_enabled=db_enabled,
        create_disk_enabled=disk_enabled,
        open_needs=open_needs,
        handoff=handoff,
        pending_resources=pending,
        can_claim_complete_success=can_complete,
        summary="; ".join(summary_parts),
    )


def build_deps_plan_body(
    view: DependencyPlanView,
    *,
    only_enabled: bool = False,
) -> dict[str, Any] | None:
    """Map dependency plan view → PlanVersion body for approve/execute."""
    steps: list[dict[str, Any]] = []
    for i, prop in enumerate(view.proposed_creates):
        if only_enabled and not prop.get("enabled"):
            continue
        # Include disabled steps as documentation in plan when not only_enabled —
        # executor will refuse write and record open-need.
        if only_enabled is False and not prop.get("enabled"):
            # Still include so approval surfaces the intent + gate.
            pass
        tool_id = str(prop["tool_id"])
        steps.append(
            {
                "id": f"dep-{i}-{prop['kind']}",
                "action": str(prop["action"]),
                "tool_id": tool_id,
                "effects": [f"provision_{prop['kind']}", "may_incur_cost"],
                "cost_known": False,
                "params": dict(prop.get("params") or {}),
            }
        )
    if not steps:
        return None
    return {
        "version": 1,
        "target_platform": None,
        "steps": steps,
        "effects": ["provision_dependencies"],
        "cost_known": False,
        "cost_summary": "unknown",
        "summary": view.summary or "Phase-4 dependency provision",
    }


_DEFAULT_DB_NAME = {"postgresql": "postgres", "postgres": "postgres", "mongodb": "admin"}


def connection_url_from_database(
    details: dict[str, Any],
    *,
    db_type: str,
    db_name: str | None = None,
) -> str | None:
    """Build a connection URL from get_database payload — caller stores via SecretService."""
    database = details.get("database") if isinstance(details.get("database"), dict) else details
    node = database.get("node") if isinstance(database.get("node"), dict) else {}
    network = database.get("network") if isinstance(database.get("network"), dict) else {}
    network_node = (
        network.get("node") if isinstance(network.get("node"), dict) else {}
    )
    # Private DBaaS: hostname on the shared network; public host may be absent.
    host = (
        node.get("host")
        or database.get("hostname")
        or network_node.get("host")
    )
    port = node.get("port") or database.get("internalPort") or 5432
    user = database.get("username") or "root"
    password = (
        node.get("root_password")
        or database.get("root_password")
        or database.get("password")
    )
    # Liara DBaaS has no per-hostname database; the hostname is not a db name.
    db_name = (
        db_name
        or database.get("dbName")
        or _DEFAULT_DB_NAME.get(db_type)
        or database.get("name")
        or "db"
    )
    if not host or password is None:
        return None
    port_s = f":{port}" if port else ""
    scheme = {
        "postgresql": "postgres",
        "postgres": "postgres",
        "mysql": "mysql",
        "mariadb": "mysql",
        "redis": "redis",
        "mongodb": "mongodb",
    }.get(db_type, db_type)
    if scheme == "redis":
        return f"redis://:{password}@{host}{port_s}/0"
    return f"{scheme}://{user}:{password}@{host}{port_s}/{db_name}"


def store_connection_secret(
    secrets: SecretService,
    *,
    workspace_id: UUID,
    kind: str,
    url: str,
    label: str,
) -> UUID:
    """Persist connection URL; never log the value."""
    _ = url  # value passed only to put
    return secrets.put(workspace_id, kind=kind, value=url, label=label)


def merge_pending_resources(
    case: Case,
    resources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach incomplete/leftover resources on Case.constraints (L-AC44)."""
    constraints = dict(case.constraints) if isinstance(case.constraints, dict) else {}
    existing = list(constraints.get("pending_resources") or [])
    by_key: dict[str, dict[str, Any]] = {}
    for item in existing + resources:
        if not isinstance(item, dict):
            continue
        key = str(
            item.get("resource_key")
            or item.get("databaseID")
            or item.get("disk_name")
            or item.get("hostname")
            or id(item)
        )
        by_key[key] = {**item, "resource_key": key}
    merged = list(by_key.values())
    constraints["pending_resources"] = merged
    case.constraints = constraints
    return merged


def clear_resolved_pending(case: Case, resource_key: str) -> None:
    constraints = dict(case.constraints) if isinstance(case.constraints, dict) else {}
    pending = [
        p
        for p in (constraints.get("pending_resources") or [])
        if isinstance(p, dict) and p.get("resource_key") != resource_key
    ]
    constraints["pending_resources"] = pending
    case.constraints = constraints


def can_claim_complete_success(
    *,
    discovery: DependencyDiscovery | None,
    pending_resources: list[dict[str, Any]] | None,
    open_needs: list[str] | None,
) -> bool:
    """Never claim full success while required deps are missing/incomplete."""
    if pending_resources:
        return False
    if open_needs and any(
        n in (DEP_OPEN_NEED_CREATE, DEP_OPEN_NEED_REQUIRED, DEP_OPEN_NEED_INCOMPLETE)
        for n in open_needs
    ):
        return False
    if discovery and discovery.required_kinds:
        # Required kinds present — success only if no open dependency needs.
        if open_needs:
            return False
    return True


def execute_dependency_steps(
    *,
    plan: PlanVersion,
    write_guard: WriteGuard,
    registry: CapabilityRegistry,
    liara_client: LiaraClient | None,
    secrets: SecretService | None,
    workspace_id: UUID,
    case: Case | None,
    prior_checkpoint: dict[str, Any] | None = None,
    session: Session | None = None,
) -> DepResult:
    """Run create_database / create_disk behind WriteGuard when registry enabled.

    Unenabled tools → handoff/open-need, zero HTTP. Incomplete creates stay on Case.
    """
    _ = session
    registry.seed()
    attempts: list[DepAttempt] = []
    provider_ids: dict[str, Any] = dict(
        (prior_checkpoint or {}).get("provider_ids") or {}
    )
    pending: list[dict[str, Any]] = list(
        (prior_checkpoint or {}).get("pending_resources") or []
    )
    if case is not None and isinstance(case.constraints, dict):
        for item in case.constraints.get("pending_resources") or []:
            if isinstance(item, dict) and item not in pending:
                pending.append(item)

    open_needs: list[str] = []
    handoff: dict[str, Any] | None = None
    write_count = 0
    state = OP_STATE_DEPS_DONE

    for step in plan.steps:
        tool_id = step.tool_id or ""
        if tool_id not in DEP_WRITE_TOOLS:
            continue
        params = dict(step.params or {})

        enabled = registry_create_enabled(registry, tool_id)
        if not enabled:
            fingerprint = request_body_fingerprint(
                {"tool_id": tool_id, "params": params, "step_id": step.id}
            )
            open_needs.append(DEP_OPEN_NEED_CREATE)
            open_needs.append(DEP_OPEN_NEED_REQUIRED)
            handoff = {
                "reason": "ld05_create_unproven",
                "message": (
                    f"{tool_id} is not enabled in the capability registry (L-D05). "
                    "No provider create was attempted."
                ),
                "next_steps": [
                    "Provision manually in Liara console, or promote tool after live proof.",
                ],
            }
            attempts.append(
                DepAttempt(
                    step_id=step.id,
                    tool_id=tool_id,
                    fingerprint=fingerprint,
                    status="blocked_registry",
                    error=DEP_OPEN_NEED_CREATE,
                )
            )
            state = OP_STATE_HANDOFF
            continue

        # Prefer explicit client; fall back to WriteGuard-injected LiaraProviderWrite (tests).
        effective_client = liara_client
        if effective_client is None and isinstance(
            write_guard._provider_write, LiaraProviderWrite  # noqa: SLF001
        ):
            effective_client = write_guard._provider_write._client  # noqa: SLF001

        if effective_client is None and not isinstance(
            write_guard._provider_write, LiaraProviderWrite  # noqa: SLF001
        ):
            # Noop guard without client cannot perform real/mocked HTTP creates.
            fingerprint = request_body_fingerprint(
                {"tool_id": tool_id, "params": params, "step_id": step.id}
            )
            attempts.append(
                DepAttempt(
                    step_id=step.id,
                    tool_id=tool_id,
                    fingerprint=fingerprint,
                    status="blocked_no_client",
                    error="liara_client_missing",
                )
            )
            open_needs.append(DEP_OPEN_NEED_REQUIRED)
            state = OP_STATE_DEPS_BLOCKED
            continue

        # Live DBaaS create needs network id + bundlePlanID from the PaaS project.
        if tool_id == "create_database" and effective_client is not None:
            project_for_db = (
                str(params.get("project_name") or "").strip()
                or str(provider_ids.get("project_name") or "").strip()
            )
            if project_for_db:
                try:
                    project = effective_client.get_project(project_for_db)
                    network = project.get("network")
                    if isinstance(network, dict) and network.get("_id"):
                        params.setdefault("network", str(network["_id"]))
                    elif isinstance(network, str) and network.strip():
                        params.setdefault("network", network.strip())
                    bundle = project.get("bundlePlanID") or project.get(
                        "bundle_plan_id"
                    )
                    if bundle:
                        params.setdefault("bundlePlanID", str(bundle))
                    # Prefer g2 plans when legacy ir-small is unavailable.
                    plan_id_val = str(
                        params.get("planID") or params.get("plan_id") or ""
                    )
                    if plan_id_val in ("ir-small", "small", "free", ""):
                        params["planID"] = _DEFAULT_PLAN_ID
                    if not params.get("version") or str(params.get("version")) in (
                        "16",
                        "17",
                    ):
                        kind_hint = str(params.get("type") or "postgres")
                        kind_key = (
                            "postgres"
                            if kind_hint in ("postgres", "postgresql")
                            else kind_hint
                        )
                        params["version"] = _DEFAULT_VERSIONS.get(
                            kind_key, "16.14"
                        )
                    provider_ids.setdefault("project_name", project_for_db)
                except LiaraClientError as exc:
                    logger.warning(
                        "could not enrich create_database from project %s: %s",
                        project_for_db,
                        exc.code,
                    )

        fingerprint = request_body_fingerprint(
            {"tool_id": tool_id, "params": params, "step_id": step.id}
        )

        try:
            result = write_guard.execute_allowlisted(tool_id=tool_id, payload=params)
            write_count += 1
        except WriteNotAllowlisted as exc:
            attempts.append(
                DepAttempt(
                    step_id=step.id,
                    tool_id=tool_id,
                    fingerprint=fingerprint,
                    status="not_allowlisted",
                    error=str(exc),
                )
            )
            state = OP_STATE_DEPS_BLOCKED
            continue
        except LiaraTimeoutError as exc:
            # Unknown outcome — track leftover intent on case (L-AC44).
            leftover = {
                "resource_key": f"unknown-{tool_id}-{step.id}",
                "tool_id": tool_id,
                "status": "unknown_after_timeout",
                "params_redacted": {
                    k: v for k, v in params.items() if k.lower() not in ("password",)
                },
                "at": _utcnow_iso(),
            }
            pending.append(leftover)
            open_needs.append(DEP_OPEN_NEED_INCOMPLETE)
            attempts.append(
                DepAttempt(
                    step_id=step.id,
                    tool_id=tool_id,
                    fingerprint=fingerprint,
                    status="unknown",
                    error=_redact_secrets_in_text(str(exc)),
                )
            )
            state = OP_STATE_UNKNOWN
            continue
        except LiaraClientError as exc:
            # 409 = already provisioned — treat as success for DevOps idempotency.
            if exc.status_code == 409 and tool_id == "create_disk":
                disk_name = params.get("name")
                project_name = params.get("project_name")
                provider_ids.setdefault("disks", []).append(
                    {"name": disk_name, "project": project_name, "existed": True}
                )
                attempts.append(
                    DepAttempt(
                        step_id=step.id,
                        tool_id=tool_id,
                        fingerprint=fingerprint,
                        status="exists",
                        provider_ids={"disk": disk_name},
                    )
                )
                continue
            if exc.status_code == 409 and tool_id == "create_database":
                hostname = str(params.get("hostname") or "")
                attempts.append(
                    DepAttempt(
                        step_id=step.id,
                        tool_id=tool_id,
                        fingerprint=fingerprint,
                        status="exists",
                        provider_ids={"hostname": hostname},
                    )
                )
                # Best-effort: resolve existing DB id for env wire below.
                if effective_client is not None and hostname:
                    try:
                        for row in effective_client.list_databases():
                            if str(row.get("hostname") or "") == hostname:
                                result = {
                                    "databaseID": row.get("_id")
                                    or row.get("id")
                                    or row.get("databaseID"),
                                    "existed": True,
                                }
                                break
                        else:
                            result = {"existed": True}
                    except LiaraClientError:
                        result = {"existed": True}
                else:
                    result = {"existed": True}
                # Fall through to secret/env wire using result.
            else:
                attempts.append(
                    DepAttempt(
                        step_id=step.id,
                        tool_id=tool_id,
                        fingerprint=fingerprint,
                        status="failed",
                        error=_redact_secrets_in_text(exc.message),
                    )
                )
                state = OP_STATE_DEPS_PARTIAL
                open_needs.append(DEP_OPEN_NEED_INCOMPLETE)
                continue

        secret_ref: str | None = None
        if tool_id == "create_database":
            database_id = result.get("databaseID") or result.get("database_id")
            hostname = params.get("hostname")
            db_type = str(params.get("type") or "postgresql")
            if database_id:
                provider_ids["databaseID"] = database_id
                provider_ids.setdefault("databases", {})[str(hostname or database_id)] = (
                    database_id
                )
            # Fetch details for connection secret (password never logged).
            if database_id and secrets is not None and effective_client is not None:
                try:
                    details = effective_client.get_database(str(database_id))
                    url = connection_url_from_database(details, db_type=db_type)
                    if url:
                        ref_id = store_connection_secret(
                            secrets,
                            workspace_id=workspace_id,
                            kind=f"db_url_{db_type}",
                            url=url,
                            label=f"dbaas:{hostname or database_id}",
                        )
                        secret_ref = str(ref_id)
                        provider_ids.setdefault("secret_refs", {})[
                            str(hostname or database_id)
                        ] = secret_ref
                        logger.info(
                            "stored DB connection secret_ref=%s hostname=%s",
                            secret_ref,
                            hostname,
                        )
                        # Wire DATABASE_URL onto the PaaS app (merge existing keys).
                        project_for_env = (
                            str(params.get("project_name") or "").strip()
                            or str(provider_ids.get("project_name") or "").strip()
                        )
                        if (
                            project_for_env
                            and url
                            and effective_client is not None
                        ):
                            try:
                                existing = effective_client.project_envs(
                                    project_for_env
                                )
                                by_key: dict[str, str] = {}
                                for row in existing:
                                    key = row.get("key") or row.get("name")
                                    val = row.get("value")
                                    if isinstance(key, str) and key.strip():
                                        by_key[key.strip()] = (
                                            str(val) if val is not None else ""
                                        )
                                by_key["DATABASE_URL"] = url
                                # Prefer real values from the local project ``.env``
                                # (DevOps UX: don't ship placeholder IMAP/SMTP when
                                # the workspace already has working secrets).
                                app_root_hint = (
                                    params.get("app_path")
                                    or provider_ids.get("app_path")
                                    or (
                                        (provider_ids.get("dependency_plan") or {}).get(
                                            "discovery", {}
                                        )
                                        if isinstance(
                                            provider_ids.get("dependency_plan"), dict
                                        )
                                        else {}
                                    ).get("app_root")
                                )
                                # discovery may live on the dependency plan checkpoint
                                if not app_root_hint and isinstance(
                                    provider_ids.get("discovery"), dict
                                ):
                                    app_root_hint = provider_ids["discovery"].get(
                                        "app_root"
                                    )
                                local_env = _load_local_dotenv_map(app_root_hint)
                                for key, val in local_env.items():
                                    if key in _LOCAL_ENV_SKIP:
                                        continue
                                    by_key[key] = val
                                # Seed required Nest/mail boot keys so the app can
                                # start; real IMAP/SMTP should be confirmed in UX.
                                # VAPID must be cryptographically valid or web-push
                                # crashes the Nest process at boot (crash-loop →
                                # Liara edge still answers hello-world ``ok``).
                                defaults = {
                                    "APP_URL": f"https://{project_for_env}.liara.run",
                                    "APP_USERNAME": "admin",
                                    "APP_PASSWORD": "change-me",
                                    "NODE_ENV": "production",
                                    "PORT": "3000",
                                    # Relative path + disk mountTo ``storage``.
                                    "STORAGE_PATH": "./storage",
                                    "IMAP_HOST": "imap.example.com",
                                    "IMAP_PORT": "993",
                                    "IMAP_USERNAME": "user@example.com",
                                    "IMAP_PASSWORD": "change-me",
                                    "IMAP_TLS": "true",
                                    "SMTP_HOST": "smtp.example.com",
                                    "SMTP_PORT": "587",
                                    "SMTP_USERNAME": "user@example.com",
                                    "SMTP_PASSWORD": "change-me",
                                    "SMTP_TLS": "true",
                                    "VAPID_PUBLIC_KEY": _BOOTSTRAP_VAPID_PUBLIC,
                                    "VAPID_PRIVATE_KEY": _BOOTSTRAP_VAPID_PRIVATE,
                                    "VAPID_SUBJECT": "mailto:admin@example.com",
                                }
                                for key, val in defaults.items():
                                    existing_val = by_key.get(key)
                                    if existing_val is None or existing_val == "":
                                        by_key[key] = val
                                    elif _is_placeholder_env_value(str(existing_val)):
                                        by_key[key] = val
                                    elif key in (
                                        "VAPID_PUBLIC_KEY",
                                        "VAPID_PRIVATE_KEY",
                                    ) and _invalid_vapid_env(
                                        key, str(existing_val)
                                    ):
                                        by_key[key] = val
                                # Platform-owned paths always win over local ./storage
                                # if the local file pointed elsewhere.
                                by_key["STORAGE_PATH"] = "./storage"
                                by_key["NODE_ENV"] = "production"
                                by_key["PORT"] = by_key.get("PORT") or "3000"
                                by_key["DATABASE_URL"] = url
                                variables = [
                                    {"key": k, "value": v}
                                    for k, v in by_key.items()
                                ]
                                write_guard.execute_allowlisted(
                                    tool_id="update_envs",
                                    payload={
                                        "project": project_for_env,
                                        "variables": variables,
                                    },
                                )
                                write_count += 1
                                provider_ids["env_wired"] = sorted(by_key.keys())
                                provider_ids["project_name"] = project_for_env
                                provider_ids["env_from_local"] = sorted(local_env.keys())
                                still_need = [
                                    k
                                    for k in (
                                        "IMAP_PASSWORD",
                                        "SMTP_PASSWORD",
                                        "APP_PASSWORD",
                                    )
                                    if _is_placeholder_env_value(by_key.get(k, ""))
                                ]
                                provider_ids["env_needs_user_secrets"] = still_need
                            except Exception as wire_exc:  # noqa: BLE001
                                logger.warning(
                                    "DATABASE_URL wire failed for %s: %s",
                                    project_for_env,
                                    type(wire_exc).__name__,
                                )
                                open_needs.append("env_wire_pending")
                                if state == OP_STATE_DEPS_DONE:
                                    state = OP_STATE_DEPS_PARTIAL
                    else:
                        pending.append(
                            {
                                "resource_key": f"db-{database_id}",
                                "databaseID": database_id,
                                "hostname": hostname,
                                "status": "created_missing_connection",
                                "at": _utcnow_iso(),
                            }
                        )
                        open_needs.append(DEP_OPEN_NEED_INCOMPLETE)
                        state = OP_STATE_DEPS_PARTIAL
                except LiaraClientError as exc:
                    pending.append(
                        {
                            "resource_key": f"db-{database_id}",
                            "databaseID": database_id,
                            "hostname": hostname,
                            "status": "created_get_failed",
                            "error": _redact_secrets_in_text(exc.message),
                            "at": _utcnow_iso(),
                        }
                    )
                    open_needs.append(DEP_OPEN_NEED_INCOMPLETE)
                    state = OP_STATE_DEPS_PARTIAL
            elif not database_id:
                pending.append(
                    {
                        "resource_key": f"db-incomplete-{step.id}",
                        "hostname": hostname,
                        "status": "create_response_missing_id",
                        "at": _utcnow_iso(),
                    }
                )
                open_needs.append(DEP_OPEN_NEED_INCOMPLETE)
                state = OP_STATE_DEPS_PARTIAL

        if tool_id == "create_disk":
            disk_name = params.get("name")
            project_name = params.get("project_name")
            provider_ids.setdefault("disks", []).append(
                {"name": disk_name, "project": project_name}
            )
            if result.get("status_code", 201) >= 400:
                pending.append(
                    {
                        "resource_key": f"disk-{project_name}-{disk_name}",
                        "disk_name": disk_name,
                        "project_name": project_name,
                        "status": "create_failed",
                        "at": _utcnow_iso(),
                    }
                )
                open_needs.append(DEP_OPEN_NEED_INCOMPLETE)
                state = OP_STATE_DEPS_PARTIAL

        attempts.append(
            DepAttempt(
                step_id=step.id,
                tool_id=tool_id,
                fingerprint=fingerprint,
                status="ok",
                provider_ids={
                    k: provider_ids[k]
                    for k in ("databaseID",)
                    if k in provider_ids
                },
                secret_ref_id=secret_ref,
            )
        )

    if case is not None and pending:
        merged = merge_pending_resources(case, pending)
        pending = merged
        # Ensure JSONB mutation is detected by SQLAlchemy.
        case.constraints = dict(case.constraints or {})
        if session is not None:
            session.flush()

    open_needs = sorted(set(open_needs))
    if write_count == 0 and state == OP_STATE_DEPS_DONE and open_needs:
        state = OP_STATE_DEPS_BLOCKED
    if pending and state == OP_STATE_DEPS_DONE:
        state = OP_STATE_DEPS_PARTIAL

    checkpoint: dict[str, Any] = {
        "open_needs": open_needs,
        "can_claim_complete_success": can_claim_complete_success(
            discovery=None,
            pending_resources=pending,
            open_needs=open_needs,
        ),
    }
    if handoff is not None:
        checkpoint["handoff"] = handoff

    return DepResult(
        state=state,
        attempts=attempts,
        provider_ids=provider_ids,
        checkpoint=checkpoint,
        write_count=write_count,
        pending_resources=pending,
    )


def build_dependency_reconnect_option(
    *,
    project_name: str,
    registry_status: dict[str, str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Phase-4 replacement for troubleshoot deferred reconnect."""
    status = (registry_status or {}).get(CREATE_DATABASE_CAP, "documented")
    enabled = status == "enabled"
    open_needs: list[str] = []
    if not enabled:
        open_needs.append(DEP_OPEN_NEED_CREATE)
    return (
        {
            "id": "fix-dep-reconnect",
            "tool_id": "dependency_reconnect",
            "label": "Reconnect / provision dependency (DB/Redis)",
            "rationale": (
                "Phase-4 path: discover + approval-gated create when registry enabled; "
                "otherwise open-need / manual handoff (L-D05)."
            ),
            "enabled": enabled,
            "disabled_reason": None if enabled else DEP_OPEN_NEED_CREATE,
            "verification_method": "dependency_ping",
            "params": {"project_name": project_name},
        },
        open_needs,
    )

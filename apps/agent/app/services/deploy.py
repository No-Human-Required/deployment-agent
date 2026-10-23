"""Phase-1 deploy path — durable Liara writes behind WriteGuard.

Algorithm (impl-plan §6):
  intent → fingerprint → HTTP → checkpoint provider IDs;
  on timeout → unknown + read-only reconcile (no blind create retry).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tarfile
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.orchestration import PlanStep, PlanVersion
from app.services.deploy_root import default_liara_app_url, resolve_deploy_app_root
from app.services.liara_client import (
    LiaraClient,
    LiaraClientError,
    LiaraNotFoundError,
    LiaraTimeoutError,
)
from app.services.write_guard import DEPLOY_WRITE_TOOLS, WriteGuard

# Hello-world / smoke stubs must not count as a real app verify.
_STUB_BODY_RE = re.compile(
    r"(?is)^\s*ok(?:\s|$).{0,80}\d{4}|hello[\s_-]?world|it works!",
)

# Skip heavy / secret / VCS paths when packing a local app for Liara sources.
_ARCHIVE_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".next",
        # ``dist`` / ``build`` are skipped by default; Nest apps that start from
        # ``dist/main.js`` re-include ``dist`` after a local pre-build below.
        "coverage",
        ".turbo",
        ".cache",
        "__pycache__",
        ".venv",
        "venv",
        ".cursor",
        ".idea",
        ".vscode",
    }
)
_ARCHIVE_SKIP_BUILD_ARTIFACTS = frozenset({"dist", "build"})
_ARCHIVE_SKIP_FILE_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        "source.tar.gz",
        ".DS_Store",
    }
)

OP_STATE_DEPLOYED = "deployed"
OP_STATE_UNKNOWN = "unknown"
OP_STATE_VERIFIED = "verified"
OP_STATE_VERIFY_FAILED = "verify_failed"
OP_STATE_AWAITING_PROVIDER = "awaiting_provider"

# Registry tool_ids promoted after successful mock proof (not enabled).
DEPLOY_REGISTRY_TOOLS = ("create_project", "sources_releases")


def live_writes_allowed() -> bool:
    """Explicit env gate for live Liara writes.

    Credentials come from workspace secrets (preferred) or ``LIARA_API_TOKEN``.
    Requiring the env token here blocked real deploys when the token was only
    stored in the companion secrets store.
    """
    flag = (os.environ.get("LIARA_ALLOW_LIVE_WRITES") or "").strip()
    return flag == "1"


def request_body_fingerprint(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def pack_app_source_archive(
    app_root: str | Path,
    *,
    dest: str | Path | None = None,
) -> Path:
    """Build a ``.tar.gz`` of the app for ``POST …/sources`` (never packs secrets).

    If ``dest`` is omitted, writes under a temp directory. Always returns an
    absolute path to an existing gzip archive.

    Liara Node always runs ``npm run build`` when that script exists. Nest apps
    that already ship ``dist/`` must rewrite ``build`` to a light step (prisma
    generate) so the platform does not re-run ``nest build`` and fail.
    """
    root = Path(app_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"app root not found: {root}")

    include_dist = _maybe_prebuild_nest_dist(root)

    if dest is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        dest_path = Path(tempfile.gettempdir()) / f"liara-src-{root.name}-{stamp}.tar.gz"
    else:
        dest_path = Path(dest).expanduser().resolve()
        dest_path.parent.mkdir(parents=True, exist_ok=True)

    skip_dirs = set(_ARCHIVE_SKIP_DIR_NAMES)
    if not include_dist:
        skip_dirs |= _ARCHIVE_SKIP_BUILD_ARTIFACTS

    # When we rewrite package.json / dist entry for PaaS, skip the on-disk copies.
    rewrite_names: set[str] = set()
    if include_dist:
        rewrite_names.add("package.json")
        if (root / "dist" / "main.js").is_file():
            rewrite_names.add("dist/main.js")

    def _filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
        parts = Path(tarinfo.name).parts
        if any(part in skip_dirs for part in parts):
            return None
        name = Path(tarinfo.name).name
        if name in _ARCHIVE_SKIP_FILE_NAMES:
            return None
        clean = parts[1:] if parts and parts[0] == "." else parts
        rel = "/".join(clean)
        if rel in rewrite_names:
            return None
        return tarinfo

    with tarfile.open(dest_path, "w:gz") as archive:
        archive.add(root, arcname=".", filter=_filter)
        if include_dist:
            _add_paas_ready_package_json(archive, root)
            _add_paas_ready_dist_main(archive, root)
        else:
            # Nest/Node apps that start from dist/* need a platform build step
            # when we could not pre-build locally.
            _maybe_add_liara_build_config(archive, root)

    if not dest_path.is_file() or dest_path.stat().st_size < 32:
        raise RuntimeError(f"packed archive empty or missing: {dest_path}")
    return dest_path


def _add_tar_bytes(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    import io

    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    archive.addfile(info, io.BytesIO(data))


def _add_paas_ready_package_json(archive: tarfile.TarFile, root: Path) -> None:
    """Rewrite scripts so Liara does not re-run a failing ``nest build``."""
    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        return
    try:
        package = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(package, dict):
        return
    scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
    scripts = dict(scripts)
    has_prisma = (root / "prisma" / "schema.prisma").is_file() or isinstance(
        scripts.get("prisma:generate"), str
    )
    # Liara runs ``npm run build`` whenever the script exists. Keep a cheap
    # build so Prisma client is generated; never re-invoke nest/tsc on PaaS.
    if has_prisma:
        scripts["build"] = "prisma generate"
        # prisma CLI is usually a devDependency — move/copy into dependencies
        # so production-style installs still generate the client.
        deps = package.get("dependencies") if isinstance(package.get("dependencies"), dict) else {}
        dev = (
            package.get("devDependencies")
            if isinstance(package.get("devDependencies"), dict)
            else {}
        )
        deps = dict(deps)
        dev = dict(dev)
        if "prisma" in dev and "prisma" not in deps:
            deps["prisma"] = dev["prisma"]
        package["dependencies"] = deps
        package["devDependencies"] = dev
    else:
        scripts["build"] = 'node -e "console.log(\'liara-agent: prebuilt dist\')"'
    # Prefer migrate-on-boot for Prisma apps so empty DBaaS gets a schema.
    start_cmd = "node dist/main.js"
    if has_prisma and (root / "prisma" / "migrations").is_dir():
        start_cmd = "prisma migrate deploy && node dist/main.js"
    scripts["start"] = start_cmd
    package["scripts"] = scripts
    data = (json.dumps(package, indent=2) + "\n").encode("utf-8")
    _add_tar_bytes(archive, "./package.json", data)


def _add_paas_ready_dist_main(archive: tarfile.TarFile, root: Path) -> None:
    """Ensure Nest listens on 0.0.0.0 (Liara PaaS requirement) in packed dist."""
    main_path = root / "dist" / "main.js"
    if not main_path.is_file():
        return
    try:
        text = main_path.read_text(encoding="utf-8")
    except OSError:
        return
    patched = text
    # Common Nest compiled shapes: app.listen(port) / app.listen(config.PORT)
    if "0.0.0.0" not in patched:
        patched = re.sub(
            r"\.listen\(\s*([^,\)]+)\s*\)",
            r'.listen(\1, "0.0.0.0")',
            patched,
            count=1,
        )
    if patched == text and "0.0.0.0" not in patched:
        # Last resort: append bind hint is not safe; keep original.
        pass
    _add_tar_bytes(archive, "./dist/main.js", patched.encode("utf-8"))


def _maybe_prebuild_nest_dist(root: Path) -> bool:
    """Run local ``prisma generate`` + ``nest build`` so the archive ships ``dist/``.

    Returns True when ``dist/main.js`` (or similar) is present and should be packed.
    """
    import subprocess

    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        return False
    try:
        package = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(package, dict):
        return False
    scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
    start = ""
    for key in ("start", "start:prod", "start:production"):
        val = scripts.get(key)
        if isinstance(val, str) and val.strip():
            start = val.strip()
            break
    if "dist/" not in start and not start.startswith("node dist"):
        return bool((root / "dist").is_dir() and any((root / "dist").glob("**/main.js")))

    dist_main = root / "dist" / "main.js"
    if dist_main.is_file():
        return True

    # Prefer existing workspace install; fall back to local install.
    env = {**os.environ, "NODE_ENV": "development"}
    try:
        if (root / "nest-cli.json").is_file():
            if (root / "prisma" / "schema.prisma").is_file():
                subprocess.run(
                    ["npx", "prisma", "generate"],
                    cwd=str(root),
                    env=env,
                    check=False,
                    capture_output=True,
                    timeout=180,
                )
            subprocess.run(
                ["npx", "nest", "build"],
                cwd=str(root),
                env=env,
                check=False,
                capture_output=True,
                timeout=300,
            )
        elif isinstance(scripts.get("build"), str):
            subprocess.run(
                ["npm", "run", "build"],
                cwd=str(root),
                env=env,
                check=False,
                capture_output=True,
                timeout=300,
            )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return dist_main.is_file()


def _maybe_add_liara_build_config(archive: tarfile.TarFile, root: Path) -> None:
    """Inject ``liara.json`` with ``npm run build`` when the app needs a compile step."""
    if (root / "liara.json").is_file():
        return
    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        return
    try:
        package = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(package, dict):
        return
    scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
    start = ""
    for key in ("start", "start:prod", "start:production"):
        val = scripts.get(key)
        if isinstance(val, str) and val.strip():
            start = val.strip()
            break
    build = scripts.get("build") if isinstance(scripts.get("build"), str) else ""
    needs_build = bool(build) and (
        "dist/" in start or "dist\\" in start or start.startswith("node dist")
    )
    if not needs_build:
        return
    # Liara often installs production-only deps; nest/prisma CLIs live in
    # devDependencies — force a full install + generate + build.
    build_parts = ["npm install --include=dev"]
    if isinstance(scripts.get("prisma:generate"), str) or (
        root / "prisma" / "schema.prisma"
    ).is_file():
        build_parts.append("npx prisma generate")
    if (root / "nest-cli.json").is_file():
        build_parts.append("npx nest build")
    elif build:
        build_parts.append("npm run build")
    payload = {
        "platform": "node",
        "port": 3000,
        "build": {"command": " && ".join(build_parts)},
    }
    data = json.dumps(payload, indent=2).encode("utf-8")
    info = tarfile.TarInfo(name="./liara.json")
    info.size = len(data)
    import io

    archive.addfile(info, io.BytesIO(data))


def ensure_deploy_archive(
    *,
    app_path: str | Path | None,
    archive_path: str | Path | None = None,
) -> str:
    """Return a usable archive path — pack from ``app_path`` when needed.

    Monorepo roots without ``scripts.start`` resolve to a runnable workspace
    package (e.g. ``apps/api``) before packing.

    When ``app_path`` is set, always re-pack into a fresh temp archive. Reusing
    a stale ``/tmp/liara-src-*.tar.gz`` previously redeployed hello-world stubs
    instead of the real app.
    """
    if app_path is not None:
        root = resolve_deploy_app_root(app_path)
        packed = pack_app_source_archive(root, dest=None)
        return str(packed)
    if archive_path is not None:
        path = Path(archive_path).expanduser()
        if path.is_file() and path.stat().st_size >= 32:
            return str(path.resolve())
    raise FileNotFoundError("no app_path or archive_path for deploy source")


@dataclass
class StepAttempt:
    step_id: str
    tool_id: str
    fingerprint: str
    status: str  # intent | sent | checkpointed | unknown | reconciled | skipped
    provider_ids: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    at: str = field(default_factory=_utcnow_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "tool_id": self.tool_id,
            "fingerprint": self.fingerprint,
            "status": self.status,
            "provider_ids": self.provider_ids,
            "error": self.error,
            "at": self.at,
        }


@dataclass
class DeployResult:
    state: str
    attempts: list[StepAttempt]
    provider_ids: dict[str, Any]
    checkpoint: dict[str, Any]
    write_count: int

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            **self.checkpoint,
            "attempts": [a.to_dict() for a in self.attempts],
            "provider_ids": self.provider_ids,
            "mode": "phase1_deploy",
            "updated_at": _utcnow_iso(),
        }


# Liara PaaS plan IDs observed from live API (free is not accepted).
DEFAULT_PAAS_PLAN_ID = "ir-small"
_LEGACY_FREE_PLAN_ALIASES = frozenset({"free", "FREE", "Free"})


def normalize_paas_plan_id(plan_id: str | None) -> str:
    raw = (plan_id or "").strip() or DEFAULT_PAAS_PLAN_ID
    if raw in _LEGACY_FREE_PLAN_ALIASES:
        return DEFAULT_PAAS_PLAN_ID
    return raw


def build_node_next_plan(
    *,
    project_name: str,
    plan_id: str = DEFAULT_PAAS_PLAN_ID,
    platform: str = "node",
    port: int = 3000,
    archive_path: str,
    summary: str | None = None,
    network: str | None = None,
    bundle_plan_id: str | None = None,
    include_create_project: bool = True,
) -> dict[str, Any]:
    """Concrete first-publish / redeploy steps for Node/Next (schema-ready dict)."""
    # Disposable demo prefix when callers forget — still allow exact names in tests.
    name = project_name
    plan_id = normalize_paas_plan_id(plan_id)
    create_params: dict[str, Any] = {
        "name": name,
        "planID": plan_id,
        "platform": platform,
        "readOnlyRootFilesystem": True,
    }
    if network:
        create_params["network"] = network
    if bundle_plan_id:
        create_params["bundlePlanID"] = bundle_plan_id
    steps: list[dict[str, Any]] = []
    effects: list[str] = []
    if include_create_project:
        steps.append(
            {
                "id": "create-project",
                "action": "create_project",
                "tool_id": "create_project",
                "effects": ["create_paas_app"],
                "cost_known": False,
                "params": create_params,
            }
        )
        effects.append("create_paas_app")
    steps.extend(
        [
            {
                "id": "upload-source",
                "action": "upload_source",
                "tool_id": "sources",
                "effects": ["upload_source_archive"],
                "cost_known": False,
                "params": {
                    "project_name": name,
                    "archive_path": archive_path,
                },
            },
            {
                "id": "create-release",
                "action": "create_release",
                "tool_id": "releases",
                "effects": ["create_release"],
                "cost_known": False,
                "params": {
                    "project_name": name,
                    "port": port,
                    "platform": platform,
                },
            },
        ]
    )
    effects.extend(["upload_source_archive", "create_release"])
    return {
        "version": 1,
        "target_platform": "next" if platform in ("next", "nextjs") else "nodejs",
        "steps": steps,
        "effects": effects,
        "cost_known": False,
        "cost_summary": "unknown",
        "summary": summary
        or (
            f"Redeploy {name} ({platform}) port={port}"
            if not include_create_project
            else f"First publish {name} ({platform}) port={port}"
        ),
    }


def _step_payload(
    step: PlanStep, *, provider_ids: dict[str, Any]
) -> dict[str, Any]:
    params = dict(step.params or {})
    tool = step.tool_id or ""
    if tool == "create_project":
        out: dict[str, Any] = {
            "name": params.get("name"),
            "planID": params.get("planID") or params.get("plan_id", "free"),
            "platform": params.get("platform", "node"),
            "readOnlyRootFilesystem": params.get("readOnlyRootFilesystem", True),
            "network": params.get("network"),
        }
        bundle = params.get("bundlePlanID") or params.get("bundle_plan_id")
        if bundle is not None:
            out["bundlePlanID"] = bundle
        return out
    if tool == "sources":
        return {
            "project_name": params.get("project_name")
            or provider_ids.get("project_name"),
            "archive_path": params.get("archive_path"),
        }
    if tool == "releases":
        disks = params.get("disks")
        if not disks:
            # Attach disks provisioned earlier in the fullstack plan.
            named = provider_ids.get("disks") or []
            if isinstance(named, list) and named:
                disks = [
                    {
                        "name": str(d.get("name") or "data"),
                        # Relative to app root — Liara Node docs prefer this with ROFS.
                        "mountTo": str(d.get("mountTo") or "storage"),
                    }
                    for d in named
                    if isinstance(d, dict)
                ]
        out: dict[str, Any] = {
            "project_name": params.get("project_name")
            or provider_ids.get("project_name"),
            "sourceID": params.get("sourceID")
            or params.get("source_id")
            or provider_ids.get("sourceID"),
            "port": params.get("port", 3000),
            "platform": params.get("platform") or params.get("type") or "node",
        }
        if disks:
            out["disks"] = disks
        return out
    return params


def execute_deploy_steps(
    *,
    plan: PlanVersion,
    write_guard: WriteGuard,
    liara_client: LiaraClient | None = None,
    prior_checkpoint: dict[str, Any] | None = None,
) -> DeployResult:
    """Run allowlisted deploy steps with durable fingerprint + reconcile-on-timeout."""
    attempts: list[StepAttempt] = []
    provider_ids: dict[str, Any] = dict(
        (prior_checkpoint or {}).get("provider_ids") or {}
    )
    write_count = 0
    state = OP_STATE_AWAITING_PROVIDER

    deploy_steps = [
        s for s in plan.steps if (s.tool_id or "") in DEPLOY_WRITE_TOOLS
    ]
    if not deploy_steps:
        return DeployResult(
            state=OP_STATE_AWAITING_PROVIDER,
            attempts=[],
            provider_ids=provider_ids,
            checkpoint={"mode": "no_deploy_steps"},
            write_count=0,
        )

    for step in deploy_steps:
        tool_id = step.tool_id or ""
        payload = _step_payload(step, provider_ids=provider_ids)

        # Ensure source archive exists before upload (always re-pack when app_path known).
        if tool_id == "sources":
            archive = payload.get("archive_path")
            app_hint = (
                payload.get("app_path")
                or provider_ids.get("app_path")
            )
            try:
                if app_hint:
                    payload["archive_path"] = ensure_deploy_archive(app_path=app_hint)
                elif archive and not Path(str(archive)).is_file():
                    raise FileNotFoundError(f"archive missing: {archive}")
                elif not archive:
                    raise FileNotFoundError("no app_path or archive_path for sources")
            except (OSError, RuntimeError, FileNotFoundError) as exc:
                attempts.append(
                    StepAttempt(
                        step_id=step.id,
                        tool_id=tool_id,
                        fingerprint=request_body_fingerprint(
                            {"tool_id": tool_id, **payload}
                        ),
                        status="failed",
                        error=f"archive_pack_failed:{type(exc).__name__}",
                    )
                )
                state = "failed"
                break

        fingerprint = request_body_fingerprint({"tool_id": tool_id, **payload})

        # Skip create only when a prior reconcile already proved the project exists
        # (do not GET-before-create — that breaks first-publish and mocks).
        if tool_id == "create_project" and provider_ids.get("project_exists"):
            project_name = str(payload.get("name") or provider_ids.get("project_name") or "")
            provider_ids["project_name"] = project_name or provider_ids.get(
                "project_name"
            )
            attempts.append(
                StepAttempt(
                    step_id=step.id,
                    tool_id=tool_id,
                    fingerprint=fingerprint,
                    status="skipped",
                    provider_ids={"project_name": project_name},
                )
            )
            continue

        attempt = StepAttempt(
            step_id=step.id,
            tool_id=tool_id,
            fingerprint=fingerprint,
            status="intent",
        )
        attempts.append(attempt)

        try:
            result = write_guard.execute_allowlisted(tool_id=tool_id, payload=payload)
            write_count += 1
            attempt.status = "checkpointed"
            attempt.provider_ids = {
                k: v
                for k, v in result.items()
                if k in ("project_name", "sourceID", "releaseID", "status_code")
            }
            if tool_id == "create_project":
                provider_ids["project_name"] = payload.get("name") or result.get(
                    "project_name"
                )
                provider_ids["project_created"] = True
            if tool_id == "sources" and result.get("sourceID"):
                provider_ids["sourceID"] = result["sourceID"]
                if payload.get("project_name"):
                    provider_ids["project_name"] = payload.get("project_name")
            if tool_id == "releases" and result.get("releaseID"):
                provider_ids["releaseID"] = result["releaseID"]
                if payload.get("project_name"):
                    provider_ids["project_name"] = payload.get("project_name")
        except LiaraTimeoutError as exc:
            attempt.status = "unknown"
            attempt.error = "timeout"
            state = OP_STATE_UNKNOWN
            reconciled = _reconcile_readonly(
                liara_client,
                project_name=str(
                    payload.get("name")
                    or payload.get("project_name")
                    or provider_ids.get("project_name")
                    or ""
                ),
                tool_id=tool_id,
                expected_release_id=provider_ids.get("releaseID"),
            )
            attempt.provider_ids = reconciled
            provider_ids.update({k: v for k, v in reconciled.items() if v is not None})
            if reconciled.get("project_exists"):
                attempt.status = "reconciled"
            # Stop further writes — no blind retry of subsequent steps.
            break
        except LiaraClientError as exc:
            # Create failed but project already on account → continue with upload/release.
            if tool_id == "create_project":
                name = str(payload.get("name") or "")
                if _is_already_exists_error(exc) or _project_exists_live(
                    liara_client, name
                ):
                    attempt.status = "skipped"
                    attempt.error = None
                    attempt.provider_ids = {
                        "project_name": name,
                        "project_exists": True,
                        "create_skipped_reason": exc.code,
                    }
                    provider_ids["project_name"] = name
                    provider_ids["project_exists"] = True
                    continue
            attempt.status = "failed"
            attempt.error = exc.code
            state = OP_STATE_UNKNOWN if exc.code == "timeout" else "failed"
            break

    if state == OP_STATE_AWAITING_PROVIDER and provider_ids.get("releaseID"):
        state = OP_STATE_DEPLOYED
    elif state == OP_STATE_AWAITING_PROVIDER and write_count > 0:
        state = OP_STATE_DEPLOYED

    project_for_url = str(provider_ids.get("project_name") or "").strip()
    if project_for_url and not provider_ids.get("app_url"):
        provider_ids["app_url"] = default_liara_app_url(project_for_url)

    return DeployResult(
        state=state,
        attempts=attempts,
        provider_ids=provider_ids,
        checkpoint={"fingerprints": [a.fingerprint for a in attempts]},
        write_count=write_count,
    )


def _project_exists_live(client: LiaraClient | None, project_name: str) -> bool:
    if not client or not project_name:
        return False
    try:
        client.get_project(project_name)
        return True
    except LiaraNotFoundError:
        return False
    except LiaraClientError:
        return False


def _is_already_exists_error(exc: LiaraClientError) -> bool:
    msg = (exc.message or str(exc) or "").lower()
    code = (exc.code or "").lower()
    if exc.status_code in (409, 422):
        return True
    return any(
        token in msg or token in code
        for token in (
            "already",
            "exist",
            "duplicate",
            "taken",
            "conflict",
            "unique",
        )
    )


def _reconcile_readonly(
    client: LiaraClient | None,
    *,
    project_name: str,
    tool_id: str,
    expected_release_id: Any = None,
) -> dict[str, Any]:
    """Read-only reconcile after unknown — never POST create again here."""
    out: dict[str, Any] = {
        "reconcile": True,
        "tool_id": tool_id,
        "project_name": project_name or None,
        "project_exists": False,
        "release_found": False,
    }
    if not client or not project_name:
        return out
    try:
        project = client.get_project(project_name)
        out["project_exists"] = True
        out["project_status"] = project.get("status")
        out["isDeployed"] = project.get("isDeployed")
    except LiaraNotFoundError:
        out["project_exists"] = False
        return out
    except LiaraClientError as exc:
        out["reconcile_error"] = exc.code
        return out

    try:
        releases = client.list_releases(project_name)
        items = releases.get("releases") if isinstance(releases, dict) else []
        if isinstance(items, list):
            out["release_count"] = len(items)
            if expected_release_id:
                out["release_found"] = any(
                    isinstance(r, dict)
                    and (
                        r.get("_id") == expected_release_id
                        or r.get("releaseID") == expected_release_id
                    )
                    for r in items
                )
            elif items:
                latest = items[0] if isinstance(items[0], dict) else {}
                out["current_release"] = latest.get("_id") or releases.get(
                    "currentRelease"
                )
                out["release_found"] = True
        if isinstance(releases, dict) and releases.get("currentRelease"):
            out["current_release"] = releases["currentRelease"]
    except LiaraClientError as exc:
        out["releases_error"] = exc.code
    return out


def _verify_url_candidates(app_url: str) -> list[str]:
    """Prefer the public root, then common Nest/Next health paths."""
    base = app_url.rstrip("/")
    paths = ("", "/api/health", "/health", "/api/healthz", "/healthz")
    out: list[str] = []
    seen: set[str] = set()
    for path in paths:
        url = base if not path else f"{base}{path}"
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def verify_deploy(
    *,
    provider_ids: dict[str, Any],
    liara_client: LiaraClient | None = None,
    app_url: str | None = None,
    http_get: Any | None = None,
    poll_attempts: int = 24,
    poll_delay_sec: float = 10.0,
    require_http: bool = True,
) -> dict[str, Any]:
    """Check release status + HTTP GET to the public app URL.

    Defaults to ``https://{project}.liara.run``. Rejects smoke/stub bodies
    (e.g. ``ok TIMESTAMP``) so a hello-world release does not count as verified.
    """
    result: dict[str, Any] = {
        "verify_mode": "phase1",
        "release_ok": False,
        "http_ok": None,
        "verified_at": _utcnow_iso(),
    }
    project_name = provider_ids.get("project_name")
    release_id = provider_ids.get("releaseID")

    # Provider-recorded releaseID means the write was accepted — not that build succeeded.
    if release_id:
        result["release_state"] = "provider_recorded"

    if liara_client and project_name:
        last_error: str | None = None
        for attempt in range(max(1, poll_attempts)):
            try:
                releases = liara_client.list_releases(str(project_name))
                items = releases.get("releases") if isinstance(releases, dict) else []
                current = (
                    releases.get("currentRelease")
                    if isinstance(releases, dict)
                    else None
                )
                if release_id and isinstance(items, list):
                    match = next(
                        (
                            r
                            for r in items
                            if isinstance(r, dict)
                            and (
                                r.get("_id") == release_id
                                or r.get("releaseID") == release_id
                            )
                        ),
                        None,
                    )
                    if match:
                        state_raw = str(match.get("state") or "").upper()
                        result["release_state"] = state_raw.lower() or "listed"
                        result["current_release"] = current
                        if state_raw in ("FAILED", "ERROR", "CANCELED", "CANCELLED"):
                            result["release_ok"] = False
                            break
                        if state_raw in ("READY", "SUCCESS", "RUNNING", "DEPLOYED"):
                            result["release_ok"] = True
                            break
                        # BUILDING / PENDING — keep polling
                        result["release_ok"] = False
                        result["release_building"] = True
                    elif current == release_id:
                        result["release_ok"] = True
                        result["release_state"] = "current"
                        result["current_release"] = current
                        break
                elif current or (isinstance(items, list) and items):
                    # Without a specific release id, presence alone is weak signal.
                    result["release_ok"] = True
                    result["release_state"] = "present"
                    result["current_release"] = current
                    break
                result["current_release"] = current
            except LiaraClientError as exc:
                last_error = exc.code
            if attempt + 1 < max(1, poll_attempts):
                time.sleep(max(0.0, poll_delay_sec))
        if last_error and not result["release_ok"]:
            result["release_error"] = last_error
        # Provider-recorded id alone is not enough when the release never became READY.
        if (
            release_id
            and result.get("release_building")
            and not result["release_ok"]
        ):
            result["release_ok"] = False
    elif release_id and not result["release_ok"]:
        # Mock path without client: provider id recorded is enough for unit proof.
        result["release_ok"] = True
        result["release_state"] = "recorded"

    url = app_url or provider_ids.get("app_url")
    if not url and project_name and require_http:
        url = default_liara_app_url(str(project_name))
    if url:
        result["app_url"] = str(url)
        getter = http_get
        if getter is None:
            import httpx

            def getter(u: str) -> tuple[int, str]:
                with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                    resp = client.get(u)
                    body = (resp.text or "")[:500]
                    return resp.status_code, body

        # Nest/global-prefix apps often 404 on ``/`` but expose ``/api/health``.
        candidates = _verify_url_candidates(str(url))
        last_error: str | None = None
        result["http_ok"] = False
        for candidate in candidates:
            try:
                raw = getter(candidate)
                if isinstance(raw, tuple):
                    status, body = int(raw[0]), str(raw[1] if len(raw) > 1 else "")
                else:
                    status, body = int(raw), ""
                result["http_status"] = status
                preview = body.strip()[:120]
                if preview:
                    result["http_body_preview"] = preview
                result["http_checked_url"] = candidate
                stub = bool(preview and _STUB_BODY_RE.search(preview))
                if stub:
                    result["http_stub_detected"] = True
                    result["http_ok"] = False
                    # Stub on the canonical URL is decisive — do not accept a
                    # later path on the same host as "verified".
                    if candidate.rstrip("/") == str(url).rstrip("/"):
                        break
                    continue
                if 200 <= status < 400:
                    result["http_ok"] = True
                    result.pop("http_stub_detected", None)
                    break
            except Exception as exc:  # noqa: BLE001 — verification soft-fail
                last_error = type(exc).__name__
        if not result.get("http_ok") and last_error and "http_status" not in result:
            result["http_error"] = last_error

    ok = bool(result["release_ok"]) and (
        result["http_ok"] is None or result["http_ok"] is True
    )
    # Live DevOps: when we have a project URL, HTTP must pass (not stub).
    if require_http and project_name and result.get("app_url"):
        ok = bool(result["release_ok"]) and result.get("http_ok") is True
    result["ok"] = ok
    return result


def promote_deploy_tools_tested(registry: Any) -> list[str]:
    """After successful mock proof: documented → tested (never enabled)."""
    updated: list[str] = []
    for tool_id in DEPLOY_REGISTRY_TOOLS:
        try:
            cap = registry.get(tool_id)
        except Exception:  # noqa: BLE001
            continue
        if cap.status == "documented":
            registry.set_status(tool_id, "tested")
            updated.append(tool_id)
    return updated

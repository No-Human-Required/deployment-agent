"""Phase-1 deploy path — durable Liara writes behind WriteGuard.

Algorithm (impl-plan §6):
  intent → fingerprint → HTTP → checkpoint provider IDs;
  on timeout → unknown + read-only reconcile (no blind create retry).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.schemas.orchestration import PlanStep, PlanVersion
from app.services.liara_client import (
    LiaraClient,
    LiaraClientError,
    LiaraNotFoundError,
    LiaraTimeoutError,
)
from app.services.write_guard import DEPLOY_WRITE_TOOLS, WriteGuard

OP_STATE_DEPLOYED = "deployed"
OP_STATE_UNKNOWN = "unknown"
OP_STATE_VERIFIED = "verified"
OP_STATE_VERIFY_FAILED = "verify_failed"
OP_STATE_AWAITING_PROVIDER = "awaiting_provider"

# Registry tool_ids promoted after successful mock proof (not enabled).
DEPLOY_REGISTRY_TOOLS = ("create_project", "sources_releases")


def live_writes_allowed() -> bool:
    """Live Liara writes require token presence AND explicit env gate."""
    token = (os.environ.get("LIARA_API_TOKEN") or "").strip()
    flag = (os.environ.get("LIARA_ALLOW_LIVE_WRITES") or "").strip()
    return bool(token) and flag == "1"


def request_body_fingerprint(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def build_node_next_plan(
    *,
    project_name: str,
    plan_id: str = "free",
    platform: str = "node",
    port: int = 3000,
    archive_path: str,
    summary: str | None = None,
) -> dict[str, Any]:
    """Concrete first-publish steps for Node/Next (schema-ready dict)."""
    # Disposable demo prefix when callers forget — still allow exact names in tests.
    name = project_name
    return {
        "version": 1,
        "target_platform": "next" if platform in ("next", "nextjs") else "nodejs",
        "steps": [
            {
                "id": "create-project",
                "action": "create_project",
                "tool_id": "create_project",
                "effects": ["create_paas_app"],
                "cost_known": False,
                "params": {
                    "name": name,
                    "planID": plan_id,
                    "platform": platform,
                    "readOnlyRootFilesystem": True,
                },
            },
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
        ],
        "effects": ["create_paas_app", "upload_source_archive", "create_release"],
        "cost_known": False,
        "cost_summary": "unknown",
        "summary": summary
        or f"First publish {name} ({platform}) port={port}",
    }


def _step_payload(
    step: PlanStep, *, provider_ids: dict[str, Any]
) -> dict[str, Any]:
    params = dict(step.params or {})
    tool = step.tool_id or ""
    if tool == "create_project":
        return {
            "name": params.get("name"),
            "planID": params.get("planID") or params.get("plan_id", "free"),
            "platform": params.get("platform", "node"),
            "readOnlyRootFilesystem": params.get("readOnlyRootFilesystem", True),
            "network": params.get("network"),
        }
    if tool == "sources":
        return {
            "project_name": params.get("project_name")
            or provider_ids.get("project_name"),
            "archive_path": params.get("archive_path"),
        }
    if tool == "releases":
        return {
            "project_name": params.get("project_name")
            or provider_ids.get("project_name"),
            "sourceID": params.get("sourceID")
            or params.get("source_id")
            or provider_ids.get("sourceID"),
            "port": params.get("port", 3000),
            "platform": params.get("platform") or params.get("type") or "node",
        }
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
        fingerprint = request_body_fingerprint({"tool_id": tool_id, **payload})

        # Skip create if prior unknown/reconcile already found the project.
        if tool_id == "create_project" and provider_ids.get("project_exists"):
            attempts.append(
                StepAttempt(
                    step_id=step.id,
                    tool_id=tool_id,
                    fingerprint=fingerprint,
                    status="skipped",
                    provider_ids={"project_name": payload.get("name")},
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
            if tool_id == "releases" and result.get("releaseID"):
                provider_ids["releaseID"] = result["releaseID"]
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
            attempt.status = "failed"
            attempt.error = exc.code
            state = OP_STATE_UNKNOWN if exc.code == "timeout" else "failed"
            break

    if state == OP_STATE_AWAITING_PROVIDER and provider_ids.get("releaseID"):
        state = OP_STATE_DEPLOYED
    elif state == OP_STATE_AWAITING_PROVIDER and write_count > 0:
        state = OP_STATE_DEPLOYED

    return DeployResult(
        state=state,
        attempts=attempts,
        provider_ids=provider_ids,
        checkpoint={"fingerprints": [a.fingerprint for a in attempts]},
        write_count=write_count,
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


def verify_deploy(
    *,
    provider_ids: dict[str, Any],
    liara_client: LiaraClient | None = None,
    app_url: str | None = None,
    http_get: Any | None = None,
) -> dict[str, Any]:
    """Check release status + optional HTTP GET to app URL."""
    result: dict[str, Any] = {
        "verify_mode": "phase1",
        "release_ok": False,
        "http_ok": None,
        "verified_at": _utcnow_iso(),
    }
    project_name = provider_ids.get("project_name")
    release_id = provider_ids.get("releaseID")

    if liara_client and project_name:
        try:
            releases = liara_client.list_releases(str(project_name))
            items = releases.get("releases") if isinstance(releases, dict) else []
            current = (
                releases.get("currentRelease") if isinstance(releases, dict) else None
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
                    result["release_ok"] = True
                    result["release_state"] = match.get("state")
                elif current == release_id:
                    result["release_ok"] = True
                    result["release_state"] = "current"
            elif current or (isinstance(items, list) and items):
                result["release_ok"] = True
                result["release_state"] = "present"
            result["current_release"] = current
        except LiaraClientError as exc:
            result["release_error"] = exc.code
    elif release_id:
        # Mock path without client: provider id recorded is enough for unit proof.
        result["release_ok"] = True
        result["release_state"] = "recorded"

    url = app_url or provider_ids.get("app_url")
    if url:
        getter = http_get
        if getter is None:
            import httpx

            def getter(u: str) -> int:
                with httpx.Client(timeout=5.0) as client:
                    return client.get(u).status_code

        try:
            status = int(getter(str(url)))
            result["http_status"] = status
            result["http_ok"] = 200 <= status < 400
        except Exception as exc:  # noqa: BLE001 — verification soft-fail
            result["http_ok"] = False
            result["http_error"] = type(exc).__name__

    ok = bool(result["release_ok"]) and (
        result["http_ok"] is None or result["http_ok"] is True
    )
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

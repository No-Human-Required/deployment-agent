"""Phase-2 ops — env/restart/resize/domain/ssl/dns behind WriteGuard.

Env (L-D03): OpenAPI documents POST /v1/projects/update-envs with ``variables``
only — no merge/replace mode. Prefer registry ``disabled`` over inventing merge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.schemas.orchestration import PlanStep, PlanVersion
from app.services.deploy import request_body_fingerprint
from app.services.liara_client import LiaraClient, LiaraClientError, LiaraTimeoutError
from app.services.write_guard import OPS_WRITE_TOOLS, WriteGuard, WriteNotAllowlisted

# Live/docs do not prove merge vs replace — keep tool disabled until proven.
ENV_CONTRACT_PROVEN = False
ENV_OPEN_NEED = "env_ld03_merge_replace_unproven"

OP_STATE_OPS_DONE = "ops_done"
OP_STATE_OPS_PARTIAL = "ops_partial"
OP_STATE_OPS_BLOCKED = "ops_blocked"
OP_STATE_UNKNOWN = "unknown"
OP_STATE_HANDOFF = "handoff"

OPS_REGISTRY_PROMOTE = ("restart_resize", "domains_ssl", "dns_records")
SSL_CERT_VALID_STATUSES = frozenset(
    {"ACTIVE", "active", "ISSUED", "issued", "VALID", "valid", "OK", "ok"}
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class EnvDiff:
    """Redacted env change view — keys only, never secret values."""

    project: str
    baseline_keys: list[str]
    proposed_keys: list[str]
    added_keys: list[str]
    changed_keys: list[str]
    removed_keys: list[str]
    contract: str  # "unproven" | "merge" | "replace"
    writable: bool
    open_need: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "baseline_keys": self.baseline_keys,
            "proposed_keys": self.proposed_keys,
            "added_keys": self.added_keys,
            "changed_keys": self.changed_keys,
            "removed_keys": self.removed_keys,
            "contract": self.contract,
            "writable": self.writable,
            "open_need": self.open_need,
        }


def redact_env_keys(envs: list[dict[str, Any]]) -> list[str]:
    keys: list[str] = []
    for item in envs:
        key = item.get("key")
        if isinstance(key, str) and key:
            keys.append(key)
    return sorted(set(keys))


def build_env_diff(
    *,
    project: str,
    baseline_envs: list[dict[str, Any]],
    proposed: list[dict[str, str]],
    assumed_contract: str | None = None,
) -> EnvDiff:
    """Compute key-level diff. Values never leave this function into the result."""
    baseline_map = {
        str(e["key"]): e.get("value")
        for e in baseline_envs
        if isinstance(e.get("key"), str)
    }
    proposed_map = {
        str(p["key"]): p.get("value")
        for p in proposed
        if isinstance(p.get("key"), str)
    }
    baseline_keys = sorted(baseline_map)
    proposed_keys = sorted(proposed_map)
    added = sorted(set(proposed_keys) - set(baseline_keys))
    removed = sorted(set(baseline_keys) - set(proposed_keys))
    changed = sorted(
        k
        for k in set(baseline_keys) & set(proposed_keys)
        if baseline_map.get(k) != proposed_map.get(k)
    )
    contract = assumed_contract or ("unproven" if not ENV_CONTRACT_PROVEN else "merge")
    writable = bool(ENV_CONTRACT_PROVEN)
    return EnvDiff(
        project=project,
        baseline_keys=baseline_keys,
        proposed_keys=proposed_keys,
        added_keys=added,
        changed_keys=changed,
        removed_keys=removed,
        contract=contract,
        writable=writable,
        open_need=None if writable else ENV_OPEN_NEED,
    )


def characterize_env_provider_semantics(
    *,
    baseline_keys: list[str],
    sent_keys: list[str],
    after_keys: list[str],
) -> str:
    """Infer merge vs replace from before/after key sets (mock or live proof)."""
    baseline = set(baseline_keys)
    sent = set(sent_keys)
    after = set(after_keys)
    unrelated = baseline - sent
    if unrelated and unrelated.isdisjoint(after):
        return "replace"
    if unrelated and unrelated.issubset(after):
        return "merge"
    if not unrelated:
        return "inconclusive"
    return "inconclusive"


@dataclass
class OpsAttempt:
    step_id: str
    tool_id: str
    fingerprint: str
    status: str
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
class OpsResult:
    state: str
    attempts: list[OpsAttempt]
    provider_ids: dict[str, Any]
    checkpoint: dict[str, Any]
    write_count: int

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            **self.checkpoint,
            "attempts": [a.to_dict() for a in self.attempts],
            "provider_ids": self.provider_ids,
            "mode": "phase2_ops",
            "updated_at": _utcnow_iso(),
        }


def build_restart_plan(*, project_name: str, reason: str | None = None) -> dict[str, Any]:
    return {
        "version": 1,
        "target_platform": None,
        "steps": [
            {
                "id": "restart",
                "action": "restart_project",
                "tool_id": "restart",
                "effects": ["restart_paas_app", "brief_interruption"],
                "cost_known": False,
                "params": {
                    "project_name": project_name,
                    "reason": reason or "operator_requested",
                },
            }
        ],
        "effects": ["restart_paas_app"],
        "cost_known": False,
        "cost_summary": "unknown",
        "summary": f"Restart {project_name}"
        + (f" ({reason})" if reason else ""),
    }


def build_resize_plan(*, project_name: str, plan_id: str) -> dict[str, Any]:
    return {
        "version": 1,
        "steps": [
            {
                "id": "resize",
                "action": "resize_project",
                "tool_id": "resize",
                "effects": ["change_plan", "possible_cost_change"],
                "cost_known": False,
                "cost_estimate": None,
                "params": {"project_name": project_name, "planID": plan_id},
            }
        ],
        "effects": ["change_plan"],
        "cost_known": False,
        "cost_summary": "unknown — prefer documenting unknown cost over inventing prices",
        "summary": f"Resize {project_name} → planID={plan_id}",
    }


def build_domain_ssl_plan(
    *,
    project_name: str,
    domain_name: str,
    provision_ssl: bool = True,
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = [
        {
            "id": "create-domain",
            "action": "create_domain",
            "tool_id": "create_domain",
            "effects": ["attach_custom_domain"],
            "cost_known": False,
            "params": {
                "name": domain_name,
                "project": project_name,
                "type": "PROJECT",
            },
        }
    ]
    if provision_ssl:
        steps.append(
            {
                "id": "provision-ssl",
                "action": "provision_ssl",
                "tool_id": "provision_ssl",
                "effects": ["ssl_request"],
                "cost_known": False,
                "params": {"domain": domain_name},
            }
        )
    return {
        "version": 1,
        "steps": steps,
        "effects": [e for s in steps for e in s["effects"]],
        "cost_known": False,
        "cost_summary": "unknown",
        "summary": f"Domain {domain_name} → {project_name}"
        + (" + SSL request" if provision_ssl else ""),
    }


def build_env_update_plan(
    *,
    project_name: str,
    variables: list[dict[str, str]],
) -> dict[str, Any]:
    """Plan for env update — executable write stays blocked until L-D03 proven."""
    # Keys only in summary; values stay in params for executor (never logged as secrets).
    keys = [str(v.get("key")) for v in variables if v.get("key")]
    return {
        "version": 1,
        "steps": [
            {
                "id": "update-envs",
                "action": "update_envs",
                "tool_id": "update_envs",
                "effects": ["update_env_vars"],
                "cost_known": False,
                "params": {
                    "project": project_name,
                    "variables": variables,
                    "keys": keys,
                },
            }
        ],
        "effects": ["update_env_vars"],
        "cost_known": False,
        "cost_summary": "unknown",
        "summary": f"Env update for {project_name} keys={keys} (L-D03 unproven → blocked)",
    }


def build_dns_record_plan(
    *,
    zone: str,
    name: str,
    record_type: str,
    contents: list[dict[str, Any]],
    ttl: int = 3600,
) -> dict[str, Any]:
    return {
        "version": 1,
        "steps": [
            {
                "id": "dns-create",
                "action": "create_dns_record",
                "tool_id": "dns_create_record",
                "effects": ["create_dns_record"],
                "cost_known": False,
                "params": {
                    "zone": zone,
                    "name": name,
                    "type": record_type,
                    "contents": contents,
                    "ttl": ttl,
                },
            }
        ],
        "effects": ["create_dns_record"],
        "cost_known": False,
        "cost_summary": "unknown",
        "summary": f"DNS {record_type} {name} @ {zone}",
    }


def release_version_diff(
    *,
    releases_payload: dict[str, Any],
    known_release_id: str | None = None,
) -> dict[str, Any]:
    """Awareness of current vs known release — read-only."""
    items = releases_payload.get("releases") if isinstance(releases_payload, dict) else []
    current = (
        releases_payload.get("currentRelease")
        if isinstance(releases_payload, dict)
        else None
    )
    latest_id = None
    if isinstance(items, list) and items:
        first = items[0] if isinstance(items[0], dict) else {}
        latest_id = first.get("_id") or first.get("releaseID")
    return {
        "current_release": current or latest_id,
        "known_release": known_release_id,
        "differs": bool(
            known_release_id
            and (current or latest_id)
            and known_release_id != (current or latest_id)
        ),
    }


def classify_domain_ssl_state(
    *,
    ssl_request_accepted: bool | None = None,
    certificates_status: str | None = None,
    domain_status: str | None = None,
) -> dict[str, Any]:
    """Distinguish SSL request accepted from cert valid (L-AC24)."""
    cert_valid = bool(
        certificates_status
        and str(certificates_status) in SSL_CERT_VALID_STATUSES
    )
    return {
        "domain_status": domain_status,
        "ssl_request_accepted": bool(ssl_request_accepted),
        "certificatesStatus": certificates_status,
        "cert_valid": cert_valid,
        # Product rule: domain success ≠ SSL acceptance alone.
        "domain_ready": domain_status is not None,
        "ssl_complete": cert_valid,
    }


def zone_owned(zones: list[dict[str, Any]], zone_name: str) -> bool:
    target = zone_name.strip().lower().rstrip(".")
    for zone in zones:
        name = zone.get("name") or zone.get("zone") or zone.get("id")
        if isinstance(name, str) and name.strip().lower().rstrip(".") == target:
            return True
    return False


def post_action_health(
    client: LiaraClient | None,
    *,
    project_name: str,
) -> dict[str, Any]:
    """Stub/mock health after restart/resize — GET project status."""
    out: dict[str, Any] = {
        "project_name": project_name,
        "checked_at": _utcnow_iso(),
        "healthy": None,
        "mode": "stub",
    }
    if not client or not project_name:
        out["healthy"] = True
        out["mode"] = "stub_no_client"
        return out
    try:
        project = client.get_project(project_name)
        status = str(project.get("status") or "").upper()
        out["status"] = status
        out["isDeployed"] = project.get("isDeployed")
        out["healthy"] = status in ("RUNNING", "STARTED", "READY", "ACTIVE") or bool(
            project.get("isDeployed")
        )
        out["mode"] = "get_project"
    except LiaraClientError as exc:
        out["healthy"] = False
        out["error"] = exc.code
    return out


def _ops_payload(step: PlanStep, *, provider_ids: dict[str, Any]) -> dict[str, Any]:
    params = dict(step.params or {})
    tool = step.tool_id or ""
    if tool == "restart":
        return {
            "project_name": params.get("project_name")
            or provider_ids.get("project_name"),
            "reason": params.get("reason"),
        }
    if tool == "resize":
        return {
            "project_name": params.get("project_name")
            or provider_ids.get("project_name"),
            "planID": params.get("planID") or params.get("plan_id"),
        }
    if tool == "create_domain":
        return {
            "name": params.get("name") or params.get("domain_name"),
            "project": params.get("project")
            or params.get("project_name")
            or provider_ids.get("project_name"),
            "type": params.get("type") or "PROJECT",
        }
    if tool == "set_domain_project":
        return {
            "domain_id": params.get("domain_id")
            or params.get("domainID")
            or provider_ids.get("domain_id"),
            "project_id": params.get("project_id")
            or params.get("projectID")
            or provider_ids.get("project_name"),
        }
    if tool == "provision_ssl":
        return {
            "domain": params.get("domain")
            or params.get("domain_name")
            or provider_ids.get("domain_name"),
        }
    if tool == "dns_create_record":
        return {
            "zone": params.get("zone"),
            "name": params.get("name"),
            "type": params.get("type") or params.get("record_type"),
            "contents": params.get("contents") or [],
            "ttl": params.get("ttl", 3600),
        }
    if tool == "update_envs":
        return {
            "project": params.get("project") or params.get("project_name"),
            "variables": params.get("variables") or [],
            "keys": params.get("keys") or [],
        }
    return params


def execute_ops_steps(
    *,
    plan: PlanVersion,
    write_guard: WriteGuard,
    liara_client: LiaraClient | None = None,
    prior_checkpoint: dict[str, Any] | None = None,
    owned_zones: list[dict[str, Any]] | None = None,
) -> OpsResult:
    """Run phase-2 allowlisted ops; block update_envs while L-D03 unproven."""
    attempts: list[OpsAttempt] = []
    provider_ids: dict[str, Any] = dict(
        (prior_checkpoint or {}).get("provider_ids") or {}
    )
    write_count = 0
    state = OP_STATE_OPS_DONE
    open_needs: list[str] = []
    env_diff: dict[str, Any] | None = None
    domain_status: dict[str, Any] | None = None
    handoff: dict[str, Any] | None = None
    health: dict[str, Any] | None = None

    ops_tools = OPS_WRITE_TOOLS | {"update_envs"}
    steps = [s for s in plan.steps if (s.tool_id or "") in ops_tools]
    if not steps:
        return OpsResult(
            state=OP_STATE_OPS_DONE,
            attempts=[],
            provider_ids=provider_ids,
            checkpoint={"mode": "no_ops_steps"},
            write_count=0,
        )

    for step in steps:
        tool_id = step.tool_id or ""
        payload = _ops_payload(step, provider_ids=provider_ids)
        fingerprint = request_body_fingerprint({"tool_id": tool_id, **_safe_fp(payload)})

        # Env: never write while contract unproven.
        if tool_id == "update_envs":
            baseline: list[dict[str, Any]] = []
            project = str(payload.get("project") or "")
            if liara_client and project:
                try:
                    baseline = liara_client.project_envs(project)
                except LiaraClientError:
                    baseline = []
            variables = [
                {"key": str(v.get("key")), "value": str(v.get("value", ""))}
                for v in (payload.get("variables") or [])
                if isinstance(v, dict) and v.get("key")
            ]
            diff = build_env_diff(
                project=project, baseline_envs=baseline, proposed=variables
            )
            env_diff = diff.to_dict()
            attempt = OpsAttempt(
                step_id=step.id,
                tool_id=tool_id,
                fingerprint=fingerprint,
                status="blocked",
                error=ENV_OPEN_NEED,
                provider_ids={"writable": False, "contract": diff.contract},
            )
            attempts.append(attempt)
            open_needs.append(ENV_OPEN_NEED)
            state = OP_STATE_OPS_BLOCKED
            continue

        # DNS: only when zone owned; else handoff (no write).
        if tool_id == "dns_create_record":
            zone = str(payload.get("zone") or "")
            zones = owned_zones
            if zones is None and liara_client is not None:
                try:
                    zones = liara_client.list_dns_zones()
                except LiaraClientError as exc:
                    zones = []
                    handoff = {
                        "reason": "dns_zones_unreadable",
                        "error": exc.code,
                        "zone": zone,
                        "message": "Cannot verify zone ownership; manual DNS handoff.",
                    }
            if zones is not None and not zone_owned(zones, zone):
                handoff = {
                    "reason": "zone_not_owned",
                    "zone": zone,
                    "message": (
                        f"Zone {zone!r} is not under this Liara DNS account. "
                        "Configure records at the registrar (manual handoff)."
                    ),
                }
                attempts.append(
                    OpsAttempt(
                        step_id=step.id,
                        tool_id=tool_id,
                        fingerprint=fingerprint,
                        status="handoff",
                        error="zone_not_owned",
                        provider_ids={"zone": zone},
                    )
                )
                state = OP_STATE_HANDOFF
                continue

        attempt = OpsAttempt(
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
                if k
                not in (
                    # never checkpoint raw env values
                    "variables",
                )
            }
            if tool_id == "restart":
                provider_ids["project_name"] = payload.get("project_name")
                provider_ids["restart_accepted"] = result.get("restart_accepted", True)
                health = post_action_health(
                    liara_client, project_name=str(payload.get("project_name") or "")
                )
                provider_ids["health"] = health
            elif tool_id == "resize":
                provider_ids["project_name"] = payload.get("project_name")
                provider_ids["planID"] = payload.get("planID")
                provider_ids["resize_accepted"] = result.get("resize_accepted", True)
                provider_ids["cost_known"] = False
                health = post_action_health(
                    liara_client, project_name=str(payload.get("project_name") or "")
                )
                provider_ids["health"] = health
            elif tool_id == "create_domain":
                provider_ids["domain_id"] = result.get("domain_id")
                provider_ids["domain_name"] = payload.get("name")
                provider_ids["project_name"] = payload.get("project")
                domain_status = classify_domain_ssl_state(
                    domain_status="created",
                    ssl_request_accepted=False,
                )
            elif tool_id == "provision_ssl":
                provider_ids["ssl_request_accepted"] = result.get(
                    "ssl_request_accepted", True
                )
                provider_ids["ssl_cert_valid"] = False
                cert_status = None
                domain_id = provider_ids.get("domain_id")
                if liara_client and domain_id:
                    try:
                        checked = liara_client.check_domain(str(domain_id))
                        cert_status = checked.get("certificatesStatus")
                        provider_ids["certificatesStatus"] = cert_status
                        provider_ids["domain_check_status"] = checked.get("status")
                    except LiaraClientError as exc:
                        provider_ids["domain_check_error"] = exc.code
                domain_status = classify_domain_ssl_state(
                    ssl_request_accepted=provider_ids.get("ssl_request_accepted"),
                    certificates_status=cert_status,
                    domain_status=str(
                        provider_ids.get("domain_check_status") or "ssl_requested"
                    ),
                )
                provider_ids["ssl_cert_valid"] = domain_status["cert_valid"]
            elif tool_id == "dns_create_record":
                provider_ids["dns_record_id"] = result.get("record_id")
                provider_ids["zone"] = payload.get("zone")
        except WriteNotAllowlisted as exc:
            attempt.status = "blocked"
            attempt.error = str(exc)
            open_needs.append(f"tool_not_allowlisted:{tool_id}")
            state = OP_STATE_OPS_BLOCKED
        except LiaraTimeoutError:
            attempt.status = "unknown"
            attempt.error = "timeout"
            state = OP_STATE_UNKNOWN
            break
        except LiaraClientError as exc:
            attempt.status = "failed"
            attempt.error = exc.code
            state = OP_STATE_OPS_PARTIAL
            break

    if write_count == 0 and state == OP_STATE_OPS_DONE and open_needs:
        state = OP_STATE_OPS_BLOCKED

    checkpoint: dict[str, Any] = {
        "fingerprints": [a.fingerprint for a in attempts],
        "open_needs": open_needs,
    }
    if env_diff is not None:
        checkpoint["env_diff"] = env_diff
    if domain_status is not None:
        checkpoint["domain_status"] = domain_status
    if handoff is not None:
        checkpoint["handoff"] = handoff
    if health is not None:
        checkpoint["health"] = health

    return OpsResult(
        state=state,
        attempts=attempts,
        provider_ids=provider_ids,
        checkpoint=checkpoint,
        write_count=write_count,
    )


def _safe_fp(payload: dict[str, Any]) -> dict[str, Any]:
    """Fingerprint without secret env values."""
    out = dict(payload)
    if "variables" in out:
        vars_ = out["variables"]
        if isinstance(vars_, list):
            out["variables"] = [
                {"key": v.get("key"), "value": "[redacted]"}
                if isinstance(v, dict)
                else v
                for v in vars_
            ]
    return out


def ensure_update_envs_disabled(registry: Any) -> str:
    """Force update_envs → disabled (L-D03 unproven). Returns resulting status."""
    cap = registry.get("update_envs")
    if cap.status == "disabled":
        return cap.status
    if cap.status == "documented":
        registry.set_status("update_envs", "disabled")
    elif cap.status == "tested":
        registry.set_status("update_envs", "disabled")
    elif cap.status == "enabled":
        registry.set_status("update_envs", "disabled")
    return registry.get("update_envs").status


def promote_ops_tools_tested(registry: Any) -> list[str]:
    """After successful mock proof: documented → tested (never enabled)."""
    updated: list[str] = []
    for tool_id in OPS_REGISTRY_PROMOTE:
        try:
            cap = registry.get(tool_id)
        except Exception:  # noqa: BLE001
            continue
        if cap.status == "documented":
            registry.set_status(tool_id, "tested")
            updated.append(tool_id)
    # Always keep env disabled while unproven.
    ensure_update_envs_disabled(registry)
    return updated

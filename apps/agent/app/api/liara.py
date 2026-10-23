"""Liara prove-read route — live me + projects; promote registry on success."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db
from app.config import Settings
from app.services.deploy_root import default_liara_app_url
from app.services.liara_client import (
    LiaraClient,
    LiaraClientError,
    LiaraNotFoundError,
    sanitize_for_log,
)
from app.services.prove_liara import prove_and_mark_tested
from app.services.registry import CapabilityNotFound
from app.services.settings import SettingsService
from app.services.troubleshoot import sanitize_log_line

router = APIRouter(prefix="/api/liara", tags=["liara"])

# Combined monitoring feed — last N sanitized lines (prompt: 50–100).
_MONITORING_LOG_LIMIT = 80


class ProveReadBody(BaseModel):
    workspace_id: uuid.UUID | None = None


def _format_plan_hint(plan: dict[str, Any]) -> str | None:
    parts: list[str] = []
    ram = plan.get("RAM") if isinstance(plan.get("RAM"), dict) else None
    cpu = plan.get("CPU") if isinstance(plan.get("CPU"), dict) else None
    if ram and ram.get("amount") is not None:
        parts.append(f"RAM {ram['amount']} GB")
    if cpu and cpu.get("amount") is not None:
        parts.append(f"CPU {cpu['amount']}")
    volume = plan.get("volume")
    if volume is not None:
        parts.append(f"Disk {volume} GB")
    return " · ".join(parts) if parts else None


def _plan_monthly_tomans(plan: dict[str, Any]) -> float | None:
    """Monthly price in Tomans — prefer displayPrice, else hourly × 720 (CLI)."""
    display = plan.get("displayPrice")
    if isinstance(display, (int, float)):
        return float(display)
    hourly = plan.get("price")
    if isinstance(hourly, (int, float)):
        return float(hourly) * 720.0
    return None


def _plan_ram_gb(plan: dict[str, Any]) -> float:
    ram = plan.get("RAM") if isinstance(plan.get("RAM"), dict) else None
    if ram and isinstance(ram.get("amount"), (int, float)):
        return float(ram["amount"])
    return 0.0


def _plan_lookup_from_me(
    me: dict[str, Any], plan_id: str | None
) -> dict[str, object] | None:
    """Resolve any plan id from GET /v1/me (no CLI free/g2 filter)."""
    if not plan_id or not str(plan_id).strip():
        return None
    pid = str(plan_id).strip()
    plans_root = me.get("plans") if isinstance(me.get("plans"), dict) else {}
    for bucket_key in ("projects", "databases"):
        bucket = plans_root.get(bucket_key)
        if not isinstance(bucket, dict):
            continue
        raw = bucket.get(pid)
        if not isinstance(raw, dict):
            continue
        ram = _plan_ram_gb(raw)
        return {
            "id": pid,
            "label": "Free" if pid == "free" else pid,
            "hint": _format_plan_hint(raw),
            "price_monthly": _plan_monthly_tomans(raw),
            "ram_gb": ram if ram > 0 else None,
        }
    return None


def _normalize_log_timestamp(raw: Any) -> str | None:
    """Turn Liara v1 datetime or v2 ns ``ts`` into an ISO-8601 UTC string."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    numeric: int | None = None
    if isinstance(raw, (int, float)):
        numeric = int(raw)
    elif isinstance(raw, str):
        stripped = raw.strip()
        if stripped.isdigit():
            numeric = int(stripped)
        else:
            return stripped or None
    if numeric is None:
        return str(raw)
    # Loki-style nanoseconds (~1e18); also accept ms (~1e12).
    if numeric >= 10**15:
        seconds = numeric / 1_000_000_000
    elif numeric >= 10**12:
        seconds = numeric / 1_000
    else:
        seconds = float(numeric)
    try:
        return (
            datetime.fromtimestamp(seconds, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except (OverflowError, OSError, ValueError):
        return str(raw)


def _public_project_plans(me: dict[str, Any]) -> list[dict[str, object]]:
    """Extract PaaS planIDs from GET /v1/me (same filter as Liara CLI)."""
    plans_root = me.get("plans") if isinstance(me.get("plans"), dict) else {}
    projects = (
        plans_root.get("projects") if isinstance(plans_root.get("projects"), dict) else {}
    )
    out: list[dict[str, object]] = []
    for plan_id, raw in projects.items():
        if not isinstance(raw, dict):
            continue
        available = bool(raw.get("available"))
        region = str(raw.get("region") or "")
        # Match liara-cli promptPlan: free + g2* Iran plans that are available.
        if not (
            available
            and (plan_id == "free" or "g2" in plan_id)
            and (not region or region == "iran")
        ):
            continue
        monthly = _plan_monthly_tomans(raw)
        ram_gb = _plan_ram_gb(raw)
        out.append(
            {
                "id": plan_id,
                "label": plan_id if plan_id != "free" else "Free",
                "hint": _format_plan_hint(raw),
                "available": available,
                "region": region or None,
                "price_monthly": monthly,
                "ram_gb": ram_gb,
                "tier": None,  # filled after sort
            }
        )
    # Weak → strong: free first, then monthly price, then RAM.
    out.sort(
        key=lambda row: (
            0 if row["id"] == "free" else 1,
            float(row.get("price_monthly") or 0),
            float(row.get("ram_gb") or 0),
            str(row["id"]),
        )
    )
    for index, row in enumerate(out):
        row["tier"] = index + 1
    return out


@router.get("/plans")
def list_plans(
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
    workspace_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    """Return selectable PaaS planIDs from live GET /v1/me."""
    settings_svc = SettingsService(db, app_settings)
    try:
        token, base_url, team_id = settings_svc.resolve_liara_credentials(workspace_id)
    except LookupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    client = LiaraClient(
        token,
        base_url=base_url,
        team_id=team_id,
        timeout=app_settings.liara_http_timeout_seconds,
    )
    try:
        me = client.get_me()
    except LiaraClientError as exc:
        raise HTTPException(status_code=502, detail=exc.to_dict()) from exc
    plans = _public_project_plans(me)
    return {"plans": plans, "source": "liara_me"}


def _public_domain_row(raw: dict[str, Any], *, project: str) -> dict[str, object] | None:
    """Normalize a Liara domain object for the companion UI (read-only)."""
    name = raw.get("name")
    if name is None or not str(name).strip():
        return None
    domain_id = raw.get("_id") or raw.get("id") or raw.get("domainID")
    return {
        "id": str(domain_id) if domain_id is not None else str(name),
        "name": str(name),
        "status": str(raw["status"]) if raw.get("status") is not None else None,
        "certificates_status": (
            str(raw["certificatesStatus"])
            if raw.get("certificatesStatus") is not None
            else None
        ),
        "project": str(raw["project"]) if raw.get("project") is not None else project,
        "type": str(raw["type"]) if raw.get("type") is not None else None,
        "cname_record": (
            str(raw["CNameRecord"]) if raw.get("CNameRecord") is not None else None
        ),
    }


@router.get("/domains")
def list_domains(
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
    project: Annotated[str, Query(min_length=1)],
    workspace_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    """List domains for a Liara project (workspace token). Read-only — no creates."""
    project_name = project.strip()
    if not project_name:
        raise HTTPException(status_code=400, detail="project is required")
    settings_svc = SettingsService(db, app_settings)
    try:
        token, base_url, team_id = settings_svc.resolve_liara_credentials(workspace_id)
    except LookupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    client = LiaraClient(
        token,
        base_url=base_url,
        team_id=team_id,
        timeout=app_settings.liara_http_timeout_seconds,
    )
    try:
        raw_domains = client.list_domains(project=project_name)
    except LiaraClientError as exc:
        raise HTTPException(status_code=502, detail=exc.to_dict()) from exc
    domains: list[dict[str, object]] = []
    for row in raw_domains:
        public = _public_domain_row(row, project=project_name)
        if public is not None:
            domains.append(public)
    return {"domains": domains, "project": project_name, "source": "liara_domains"}


def _public_project_detail(raw: dict[str, Any], *, fallback_name: str) -> dict[str, object]:
    """Sanitize GET /v1/projects/{name} for the monitoring UI (read-only)."""
    name = raw.get("name") or raw.get("project_id") or fallback_name
    project_id = raw.get("project_id") or raw.get("_id") or raw.get("id") or name
    plan_id = raw.get("planID") or raw.get("planId") or raw.get("plan")
    scale = raw.get("scale")
    app_name = str(name)
    return {
        "name": app_name,
        "project_id": str(project_id) if project_id is not None else app_name,
        "type": str(raw["type"]) if raw.get("type") is not None else None,
        "status": str(raw["status"]) if raw.get("status") is not None else None,
        "isDeployed": bool(raw["isDeployed"]) if raw.get("isDeployed") is not None else None,
        "plan_id": str(plan_id) if plan_id is not None else None,
        "region": str(raw["region"]) if raw.get("region") is not None else None,
        "scale": int(scale) if isinstance(scale, (int, float)) else None,
        "default_url": default_liara_app_url(app_name),
        "kind": "app",
    }


def _coerce_metric_number(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw.strip())
        except ValueError:
            return None
    return None


def _latest_from_values_pairs(values: list[Any]) -> float | None:
    """Liara series points are ``[timestamp, \"0.12\"]`` pairs."""
    for point in reversed(values):
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            num = _coerce_metric_number(point[1])
            if num is not None:
                return num
        if isinstance(point, dict):
            for key in ("v", "value", "cpu", "memory", "usage", "y"):
                num = _coerce_metric_number(point.get(key))
                if num is not None:
                    return num
        num = _coerce_metric_number(point)
        if num is not None:
            return num
    return None


def _latest_metric_value(payload: dict[str, Any] | list[Any] | None) -> float | None:
    """Extract the newest numeric sample from Liara metrics shapes."""
    if payload is None:
        return None
    if isinstance(payload, list):
        return _latest_from_values_pairs(payload)
    if not isinstance(payload, dict):
        return None
    # Live shape: { end, result: [ { values: [[t, v], ...], applet }, ... ] }
    result = payload.get("result")
    if isinstance(result, list):
        best: float | None = None
        for series in result:
            if not isinstance(series, dict):
                continue
            values = series.get("values")
            if isinstance(values, list):
                candidate = _latest_from_values_pairs(values)
                if candidate is not None:
                    best = candidate if best is None else max(best, candidate)
        if best is not None:
            return best
    for key in ("data", "metrics", "values", "series", "points"):
        nested = payload.get(key)
        if isinstance(nested, list) and nested:
            found = _latest_from_values_pairs(nested)
            if found is not None:
                return found
    return None


def _latest_from_summary(
    summary: dict[str, Any] | None,
    *,
    usage_key: str,
) -> float | None:
    """Parse ``metrics/summary`` ``cpuUsage`` / ``memoryUsage`` rows."""
    if not summary:
        return None
    rows = summary.get(usage_key)
    if not isinstance(rows, list) or not rows:
        return None
    best: float | None = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = row.get("value")
        # value is [timestamp, "0.12"] or nested list
        if isinstance(value, list) and len(value) >= 2:
            num = _coerce_metric_number(value[1])
        elif isinstance(value, list) and value and isinstance(value[0], list):
            num = _latest_from_values_pairs(value)
        else:
            num = _coerce_metric_number(value)
        if num is not None:
            best = num if best is None else max(best, num)
    return best


def _metrics_series_present(payload: dict[str, Any] | list[Any] | None) -> bool:
    """True when Liara returned a usable metrics payload (empty ≠ success)."""
    if payload is None:
        return False
    if isinstance(payload, list):
        return len(payload) > 0
    if isinstance(payload, dict):
        if not payload:
            return False
        result = payload.get("result")
        if isinstance(result, list) and any(
            isinstance(row, dict)
            and isinstance(row.get("values"), list)
            and len(row["values"]) > 0
            for row in result
        ):
            return True
        for key in ("data", "metrics", "values", "series", "points"):
            val = payload.get(key)
            if isinstance(val, list) and len(val) > 0:
                return True
            if isinstance(val, dict) and val:
                return True
        # Non-empty dict without known series keys — treat as thin-but-present.
        return True
    return False


def _public_metrics_block(
    payload: dict[str, Any] | list[Any] | None,
    *,
    source: str,
    gaps: list[dict[str, object]],
    latest_override: float | None = None,
) -> dict[str, object]:
    """Wrap CPU/memory series or record an explicit gap."""
    latest = latest_override if latest_override is not None else _latest_metric_value(payload)
    if not _metrics_series_present(payload) and latest is None:
        gaps.append(
            {
                "source": source,
                "reason": "missing_or_empty",
                "message": f"{source} metrics unavailable from Liara API",
            }
        )
        return {"available": False, "series": None, "latest": None}
    return {
        "available": True,
        "series": payload if _metrics_series_present(payload) else None,
        "latest": latest,
    }


def _public_app_service_row(raw: dict[str, Any]) -> dict[str, object] | None:
    project_id = raw.get("project_id") or raw.get("name")
    if project_id is None or not str(project_id).strip():
        return None
    status = raw.get("status")
    return {
        "id": str(project_id),
        "name": str(project_id),
        "kind": "app",
        "type": str(raw["type"]) if raw.get("type") is not None else "unknown",
        "status": str(status) if status is not None else (
            "deployed" if raw.get("isDeployed") else "unknown"
        ),
        "isDeployed": bool(raw["isDeployed"]) if raw.get("isDeployed") is not None else None,
        "plan_id": (
            str(raw["planID"])
            if raw.get("planID") is not None
            else (str(raw["planId"]) if raw.get("planId") is not None else None)
        ),
        "region": str(raw["region"]) if raw.get("region") is not None else None,
    }


def _public_database_service_row(raw: dict[str, Any]) -> dict[str, object] | None:
    db_id = raw.get("id") or raw.get("_id") or raw.get("DBId") or raw.get("databaseID")
    hostname = raw.get("hostname") or raw.get("name") or raw.get("displayName")
    if db_id is None and hostname is None:
        return None
    status = raw.get("status") or raw.get("state")
    return {
        "id": str(db_id or hostname),
        "name": str(hostname or db_id),
        "kind": "database",
        "type": str(raw.get("type") or raw.get("databaseType") or "database"),
        "status": str(status) if status is not None else "unknown",
        "isDeployed": None,
        "plan_id": str(raw["planID"]) if raw.get("planID") is not None else None,
        "region": str(raw["region"]) if raw.get("region") is not None else None,
    }


def _public_database_detail(raw: dict[str, Any], *, fallback_id: str) -> dict[str, object]:
    """Sanitize GET /v1/databases/{id} — never expose passwords."""
    database = raw.get("database") if isinstance(raw.get("database"), dict) else raw
    db_id = (
        database.get("id")
        or database.get("_id")
        or database.get("DBId")
        or fallback_id
    )
    hostname = database.get("hostname") or database.get("name") or db_id
    plan_id = database.get("planID") or database.get("planId")
    scale = database.get("scale")
    volume = database.get("volumeSize")
    return {
        "name": str(hostname),
        "project_id": str(db_id),
        "type": str(database["type"]) if database.get("type") is not None else None,
        "status": str(database["status"]) if database.get("status") is not None else None,
        "isDeployed": None,
        "plan_id": str(plan_id) if plan_id is not None else None,
        "region": str(database["region"]) if database.get("region") is not None else None,
        "scale": int(scale) if isinstance(scale, (int, float)) else None,
        "version": str(database["version"]) if database.get("version") is not None else None,
        "volume_size_gb": float(volume) if isinstance(volume, (int, float)) else None,
        "public_network": (
            bool(database["publicNetwork"])
            if database.get("publicNetwork") is not None
            else None
        ),
        "kind": "database",
    }


def _public_log_lines(
    logs: list[dict[str, Any]],
    *,
    gaps: list[dict[str, object]],
    limit: int = _MONITORING_LOG_LIMIT,
) -> dict[str, object]:
    """Cap + sanitize log messages; empty list → explicit gap.

    Accepts v1-shaped rows (``datetime`` / ``message``) and v2 runtime rows
    (``ts`` nanoseconds, ``stream``, ``message``).
    """
    if not logs:
        gaps.append(
            {
                "source": "logs",
                "reason": "empty",
                "message": "No recent log lines from Liara API",
            }
        )
        return {"available": False, "lines": [], "truncated": False}

    lines: list[dict[str, object]] = []
    for entry in logs[-limit:]:
        raw_msg = entry.get("message")
        if isinstance(raw_msg, str):
            message, _was_injection = sanitize_log_line(raw_msg)
        elif raw_msg is not None:
            message = sanitize_for_log(str(raw_msg), limit=400)
        else:
            message = ""
        if not message:
            continue
        ts = (
            entry.get("datetime")
            or entry.get("createdAt")
            or entry.get("timestamp")
            or entry.get("time")
            or entry.get("ts")
        )
        stream = entry.get("stream")
        row: dict[str, object] = {
            "message": message,
            "timestamp": _normalize_log_timestamp(ts),
        }
        if isinstance(stream, str) and stream.strip():
            row["stream"] = stream.strip()
        lines.append(row)

    if not lines:
        gaps.append(
            {
                "source": "logs",
                "reason": "empty_after_sanitize",
                "message": "Log lines present but none usable after sanitization",
            }
        )
        return {"available": False, "lines": [], "truncated": False}

    truncated = len(logs) > limit
    return {"available": True, "lines": lines, "truncated": truncated}


def _soft_monitoring_domains(
    client: LiaraClient,
    *,
    project_name: str,
    gaps: list[dict[str, object]],
) -> list[dict[str, object]]:
    """List domains for a project; failures become soft gaps."""
    try:
        raw_domains = client.list_domains(project=project_name)
    except LiaraClientError as exc:
        _append_client_gap(gaps, source="domains", exc=exc)
        return []
    domains: list[dict[str, object]] = []
    for row in raw_domains:
        if not isinstance(row, dict):
            continue
        public = _public_domain_row(row, project=project_name)
        if public is not None:
            domains.append(public)
    return domains


def _soft_monitoring_plan(
    client: LiaraClient,
    *,
    plan_id: str | None,
    gaps: list[dict[str, object]],
) -> dict[str, object] | None:
    """Lookup active plan price/hint from /v1/me; failures become soft gaps."""
    if not plan_id:
        return None
    try:
        me = client.get_me()
    except LiaraClientError as exc:
        _append_client_gap(gaps, source="plan", exc=exc)
        return None
    return _plan_lookup_from_me(me, plan_id)


def _append_client_gap(
    gaps: list[dict[str, object]],
    *,
    source: str,
    exc: LiaraClientError,
) -> None:
    gaps.append(
        {
            "source": source,
            "reason": exc.code,
            "message": sanitize_for_log(exc.message, limit=200) or f"{source} unavailable",
        }
    )


def _liara_client_for_workspace(
    db: Session,
    app_settings: Settings,
    workspace_id: uuid.UUID | None,
) -> LiaraClient:
    settings_svc = SettingsService(db, app_settings)
    try:
        token, base_url, team_id = settings_svc.resolve_liara_credentials(workspace_id)
    except LookupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LiaraClient(
        token,
        base_url=base_url,
        team_id=team_id,
        timeout=app_settings.liara_http_timeout_seconds,
    )


@router.get("/services")
def list_services(
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
    workspace_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    """Account catalog: PaaS apps + DBaaS databases (read-only)."""
    client = _liara_client_for_workspace(db, app_settings, workspace_id)
    services: list[dict[str, object]] = []
    try:
        for row in client.list_projects():
            public = _public_app_service_row(row)
            if public is not None:
                services.append(public)
    except LiaraClientError as exc:
        raise HTTPException(status_code=502, detail=exc.to_dict()) from exc

    try:
        for row in client.list_databases():
            public = _public_database_service_row(row)
            if public is not None:
                services.append(public)
    except LiaraClientError as exc:
        # Apps already listed — surface DBaaS as a soft gap rather than failing the page.
        return {
            "services": services,
            "source": "liara_services",
            "gaps": [
                {
                    "source": "databases",
                    "reason": exc.code,
                    "message": sanitize_for_log(exc.message, limit=200)
                    or "databases unavailable",
                }
            ],
        }

    return {"services": services, "source": "liara_services", "gaps": []}


@router.get("/projects/{name}/monitoring")
def get_project_monitoring(
    name: str,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
    workspace_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    """Combined project detail + CPU/memory metrics + recent logs (read-only).

    Metrics calls pass the required Liara ``since`` Unix timestamp (default: 1h ago).
    ``cpu.latest`` / ``memory.latest`` prefer ``metrics/summary`` when present.
    """
    project_name = name.strip()
    if not project_name:
        raise HTTPException(status_code=400, detail="project name is required")

    client = _liara_client_for_workspace(db, app_settings, workspace_id)

    try:
        raw_project = client.get_project(project_name)
    except LiaraNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.to_dict()) from exc
    except LiaraClientError as exc:
        raise HTTPException(status_code=502, detail=exc.to_dict()) from exc

    gaps: list[dict[str, object]] = []
    project = _public_project_detail(raw_project, fallback_name=project_name)

    summary: dict[str, Any] | None = None
    try:
        summary = client.get_metrics_summary(project_name)
    except LiaraClientError as exc:
        _append_client_gap(gaps, source="summary", exc=exc)

    # Metrics / logs: soft gaps on empty or client errors (do not invent series).
    try:
        cpu_raw = client.get_cpu_metrics(project_name)
        cpu = _public_metrics_block(
            cpu_raw,
            source="cpu",
            gaps=gaps,
            latest_override=_latest_from_summary(summary, usage_key="cpuUsage"),
        )
    except LiaraClientError as exc:
        _append_client_gap(gaps, source="cpu", exc=exc)
        latest = _latest_from_summary(summary, usage_key="cpuUsage")
        cpu = {
            "available": latest is not None,
            "series": None,
            "latest": latest,
        }

    try:
        memory_raw = client.get_memory_metrics(project_name)
        memory = _public_metrics_block(
            memory_raw,
            source="memory",
            gaps=gaps,
            latest_override=_latest_from_summary(summary, usage_key="memoryUsage"),
        )
    except LiaraClientError as exc:
        _append_client_gap(gaps, source="memory", exc=exc)
        latest = _latest_from_summary(summary, usage_key="memoryUsage")
        memory = {
            "available": latest is not None,
            "series": None,
            "latest": latest,
        }

    try:
        raw_logs = client.get_runtime_logs(project_name)
        logs = _public_log_lines(raw_logs, gaps=gaps)
    except LiaraClientError as exc:
        _append_client_gap(gaps, source="logs", exc=exc)
        logs = {"available": False, "lines": [], "truncated": False}

    domains = _soft_monitoring_domains(
        client, project_name=project_name, gaps=gaps
    )
    plan = _soft_monitoring_plan(
        client,
        plan_id=str(project["plan_id"]) if project.get("plan_id") else None,
        gaps=gaps,
    )

    return {
        "project": project,
        "plan": plan,
        "domains": domains,
        "cpu": cpu,
        "memory": memory,
        "logs": logs,
        "gaps": gaps,
        "source": "liara_monitoring",
    }


@router.get("/databases/{database_id}/monitoring")
def get_database_monitoring(
    database_id: str,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
    workspace_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    """DBaaS detail for the monitoring pane (no app metrics/logs on this API)."""
    db_id = database_id.strip()
    if not db_id:
        raise HTTPException(status_code=400, detail="database id is required")

    client = _liara_client_for_workspace(db, app_settings, workspace_id)
    try:
        raw = client.get_database(db_id)
    except LiaraNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.to_dict()) from exc
    except LiaraClientError as exc:
        raise HTTPException(status_code=502, detail=exc.to_dict()) from exc

    project = _public_database_detail(raw, fallback_id=db_id)
    gaps: list[dict[str, object]] = [
        {
            "source": "cpu",
            "reason": "not_applicable",
            "message": "CPU metrics are not exposed for DBaaS via this API",
        },
        {
            "source": "memory",
            "reason": "not_applicable",
            "message": "Memory metrics are not exposed for DBaaS via this API",
        },
        {
            "source": "logs",
            "reason": "not_applicable",
            "message": "Runtime logs are not exposed for DBaaS via this API",
        },
        {
            "source": "domains",
            "reason": "not_applicable",
            "message": "Custom domains are not listed for DBaaS via this API",
        },
    ]
    plan = _soft_monitoring_plan(
        client,
        plan_id=str(project["plan_id"]) if project.get("plan_id") else None,
        gaps=gaps,
    )
    return {
        "project": project,
        "plan": plan,
        "domains": [],
        "cpu": {"available": False, "series": None, "latest": None},
        "memory": {"available": False, "series": None, "latest": None},
        "logs": {"available": False, "lines": [], "truncated": False},
        "gaps": gaps,
        "source": "liara_database_monitoring",
    }


@router.post("/prove-read")
def prove_read(
    body: ProveReadBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    try:
        outcome = prove_and_mark_tested(
            db,
            workspace_id=body.workspace_id,
            settings=app_settings,
        )
    except CapabilityNotFound as exc:
        # Subclass of LookupError — must be caught before the generic branch.
        raise HTTPException(
            status_code=503,
            detail=f"capability registry missing {exc}; run seed_registry",
        ) from exc
    except LookupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LiaraClientError as exc:
        raise HTTPException(
            status_code=502,
            detail=exc.to_dict(),
        ) from exc
    return outcome.model_dump()

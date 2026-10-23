"""Liara prove-read route — live me + projects; promote registry on success."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db
from app.config import Settings
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
    return {
        "name": str(name),
        "project_id": str(project_id) if project_id is not None else str(name),
        "type": str(raw["type"]) if raw.get("type") is not None else None,
        "status": str(raw["status"]) if raw.get("status") is not None else None,
        "isDeployed": bool(raw["isDeployed"]) if raw.get("isDeployed") is not None else None,
        "plan_id": str(plan_id) if plan_id is not None else None,
        "region": str(raw["region"]) if raw.get("region") is not None else None,
    }


def _metrics_series_present(payload: dict[str, Any] | list[Any] | None) -> bool:
    """True when Liara returned a usable metrics payload (empty ≠ success)."""
    if payload is None:
        return False
    if isinstance(payload, list):
        return len(payload) > 0
    if isinstance(payload, dict):
        if not payload:
            return False
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
) -> dict[str, object]:
    """Wrap CPU/memory series or record an explicit gap."""
    if not _metrics_series_present(payload):
        gaps.append(
            {
                "source": source,
                "reason": "missing_or_empty",
                "message": f"{source} metrics unavailable from Liara API",
            }
        )
        return {"available": False, "series": None}
    return {"available": True, "series": payload}


def _public_log_lines(
    logs: list[dict[str, Any]],
    *,
    gaps: list[dict[str, object]],
    limit: int = _MONITORING_LOG_LIMIT,
) -> dict[str, object]:
    """Cap + sanitize log messages; empty list → explicit gap."""
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
        )
        lines.append(
            {
                "message": message,
                "timestamp": str(ts) if ts is not None else None,
            }
        )

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


@router.get("/projects/{name}/monitoring")
def get_project_monitoring(
    name: str,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
    workspace_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    """Combined project detail + CPU/memory metrics + recent logs (read-only).

    Response shape::

        {
          "project": { name, project_id, type, status, isDeployed, plan_id, region },
          "cpu": { "available": bool, "series": object|list|null },
          "memory": { "available": bool, "series": object|list|null },
          "logs": { "available": bool, "lines": [...], "truncated": bool },
          "gaps": [{ "source", "reason", "message" }, ...],
          "source": "liara_monitoring"
        }

    Project fetch failures map to 404 (not found) or 502 (other Liara errors).
    Missing/unsupported metrics or logs become ``available: false`` + ``gaps``
    entries — they do not crash the response.
    """
    project_name = name.strip()
    if not project_name:
        raise HTTPException(status_code=400, detail="project name is required")

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
        raw_project = client.get_project(project_name)
    except LiaraNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.to_dict()) from exc
    except LiaraClientError as exc:
        raise HTTPException(status_code=502, detail=exc.to_dict()) from exc

    gaps: list[dict[str, object]] = []
    project = _public_project_detail(raw_project, fallback_name=project_name)

    # Metrics / logs: soft gaps on empty or client errors (do not invent series).
    try:
        cpu_raw = client.get_cpu_metrics(project_name)
        cpu = _public_metrics_block(cpu_raw, source="cpu", gaps=gaps)
    except LiaraClientError as exc:
        _append_client_gap(gaps, source="cpu", exc=exc)
        cpu = {"available": False, "series": None}

    try:
        memory_raw = client.get_memory_metrics(project_name)
        memory = _public_metrics_block(memory_raw, source="memory", gaps=gaps)
    except LiaraClientError as exc:
        _append_client_gap(gaps, source="memory", exc=exc)
        memory = {"available": False, "series": None}

    try:
        raw_logs = client.get_logs(project_name)
        logs = _public_log_lines(raw_logs, gaps=gaps)
    except LiaraClientError as exc:
        _append_client_gap(gaps, source="logs", exc=exc)
        logs = {"available": False, "lines": [], "truncated": False}

    return {
        "project": project,
        "cpu": cpu,
        "memory": memory,
        "logs": logs,
        "gaps": gaps,
        "source": "liara_monitoring",
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

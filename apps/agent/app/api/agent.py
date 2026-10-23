"""Autonomous DevOps agent runs — start, stream (SSE), snapshot, resume after approval."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.agent.runs import RunNotFound, RunStateError, registry
from app.models.conversation import WorkspaceFolder
from app.services.llm import LlmNotConfigured
from app.services.settings import SettingsService

router = APIRouter(prefix="/api/agent", tags=["agent"])

_HEARTBEAT_SECONDS = 15.0


class StartRunBody(BaseModel):
    workspace_id: uuid.UUID | None = None
    conversation_id: str | None = None
    goal: str = Field(min_length=1, max_length=4000)
    project_root: str | None = None
    project_name: str | None = None


class ResumeBody(BaseModel):
    approved: bool
    note: str | None = Field(default=None, max_length=1000)


class SteerBody(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")[:32] or "app"


@router.post("/runs")
def start_run(body: StartRunBody, db: Annotated[Session, Depends(get_db)]) -> dict[str, object]:
    workspace = SettingsService(db).resolve_workspace(body.workspace_id)
    project_root = body.project_root
    if not project_root:
        folder = db.scalar(
            select(WorkspaceFolder).where(
                WorkspaceFolder.workspace_id == workspace.id, WorkspaceFolder.is_active.is_(True)
            )
        )
        if folder is None:
            raise HTTPException(status_code=400, detail="no project folder selected")
        project_root = folder.path
    project_name = (body.project_name or "").strip() or _slug(project_root.rstrip("/").split("/")[-1])
    db.commit()
    try:
        run = registry.create(
            workspace_id=workspace.id,
            goal=body.goal,
            project_root=project_root,
            project_name=project_name,
            conversation_id=body.conversation_id,
        )
    except LlmNotConfigured as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RunStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"run_id": run.run_id, "status": run.status, "project_name": run.project_name, "project_root": run.project_root}


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    try:
        return registry.get(run_id).snapshot()
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


@router.get("/runs/{run_id}/events")
def stream_events(run_id: str, after: Annotated[int, Query(ge=0)] = 0) -> StreamingResponse:
    try:
        run = registry.get(run_id)
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc

    def generate() -> Iterator[str]:
        seq = after
        yield "retry: 3000\n\n"
        while True:
            batch = run.events_after(seq, timeout=_HEARTBEAT_SECONDS)
            for event in batch:
                seq = int(event["seq"])
                yield f"id: {seq}\ndata: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            if run.finished and seq >= len(run.events):
                return
            if not batch:
                yield ": keep-alive\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/runs/{run_id}/resume")
def resume_run(run_id: str, body: ResumeBody) -> dict[str, object]:
    try:
        run = registry.get(run_id)
        run.resume(approved=body.approved, note=body.note)
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    except RunStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"run_id": run.run_id, "status": run.status}


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str) -> dict[str, object]:
    try:
        run = registry.get(run_id)
        run.cancel()
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    except RunStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"run_id": run.run_id, "status": run.status}


@router.post("/runs/{run_id}/message")
def steer_run(run_id: str, body: SteerBody) -> dict[str, object]:
    """Send a mid-run chat follow-up; applied on the agent's next decision turn."""
    try:
        run = registry.get(run_id)
        stored = run.steer(body.message)
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    except RunStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run_id": run.run_id, "status": run.status, "message": stored}

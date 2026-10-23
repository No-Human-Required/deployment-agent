"""In-process agent runs: background thread per run, buffered events for SSE, HITL resume."""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.agent.context import AgentContext, Budget
from app.agent.graph import build_agent_graph, recursion_limit_for
from app.config import Settings, get_settings
from app.db.session import session_scope
from app.models.audit import AuditEvent
from app.services.deploy import live_writes_allowed
from app.services.liara_client import LiaraClient
from app.services.llm import LlmService
from app.services.settings import SettingsService
from app.services.write_guard import WriteGuard

STATUS_RUNNING = "running"
STATUS_AWAITING = "awaiting_approval"
STATUS_DONE = "done"
STATUS_ERROR = "error"


class RunNotFound(LookupError):
    pass


class RunStateError(RuntimeError):
    pass


@dataclass
class AgentRun:
    run_id: str
    workspace_id: uuid.UUID
    goal: str
    project_root: str
    project_name: str
    conversation_id: str | None = None
    status: str = STATUS_RUNNING
    events: list[dict[str, Any]] = field(default_factory=list)
    outcome: dict[str, Any] | None = None
    pending_approval: dict[str, Any] | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    _cond: threading.Condition = field(default_factory=threading.Condition, repr=False)
    _graph: Any = field(default=None, repr=False)
    _ctx: AgentContext | None = field(default=None, repr=False)

    def emit(self, event: dict[str, Any]) -> None:
        with self._cond:
            self.events.append({**event, "seq": len(self.events) + 1, "ts": time.time()})
            self._cond.notify_all()

    def events_after(self, seq: int, *, timeout: float) -> list[dict[str, Any]]:
        with self._cond:
            if len(self.events) <= seq and not self.finished:
                self._cond.wait(timeout=timeout)
            return self.events[seq:]

    @property
    def finished(self) -> bool:
        return self.status in (STATUS_DONE, STATUS_ERROR)

    def snapshot(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workspace_id": str(self.workspace_id),
            "conversation_id": self.conversation_id,
            "goal": self.goal,
            "project_root": self.project_root,
            "project_name": self.project_name,
            "status": self.status,
            "outcome": self.outcome,
            "pending_approval": self.pending_approval,
            "events": self.events,
            "created_at": self.created_at,
        }

    @property
    def _config(self) -> dict[str, Any]:
        assert self._ctx is not None
        return {"configurable": {"thread_id": self.run_id}, "recursion_limit": recursion_limit_for(self._ctx)}

    def _drive(self, graph_input: Any) -> None:
        try:
            interrupted: dict[str, Any] | None = None
            for chunk in self._graph.stream(graph_input, self._config, stream_mode="updates"):
                if "__interrupt__" in chunk:
                    payload = chunk["__interrupt__"][0].value
                    interrupted = payload if isinstance(payload, dict) else {"value": payload}
                if self._ctx is not None and self._ctx.cancelled:
                    self._finish_cancelled()
                    return
            if interrupted is not None:
                self.pending_approval = interrupted
                self.status = STATUS_AWAITING
                self.emit({"type": "approval_required", **interrupted})
                return
            values = self._graph.get_state(self._config).values
            self.outcome = values.get("outcome") or {"success": False, "summary": "اجرا بدون نتیجه پایان یافت."}
            self.status = STATUS_DONE
            self._audit("agent.run_finished", {"success": self.outcome.get("success"), "verified": self.outcome.get("verified")})
            self.emit({"type": "done", "outcome": self.outcome})
        except Exception as exc:  # noqa: BLE001 — reported to the UI, never swallowed silently
            self.status = STATUS_ERROR
            self.outcome = {"success": False, "summary": f"خطای داخلی agent: {type(exc).__name__}: {exc}"}
            traceback.print_exc()
            self.emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"[:500]})
        finally:
            with self._cond:
                self._cond.notify_all()

    def _audit(self, event_type: str, payload: dict[str, Any]) -> None:
        try:
            with session_scope() as session:
                session.add(
                    AuditEvent(
                        workspace_id=self.workspace_id,
                        event_type=event_type,
                        payload={"run_id": self.run_id, **payload},
                        actor="devops-agent",
                    )
                )
        except Exception:  # noqa: BLE001 — audit failure must not kill the run
            traceback.print_exc()

    def start(self) -> None:
        message = HumanMessage(
            f"{self.goal}\n\nProject folder: {self.project_root}\nLiara app: {self.project_name}"
        )
        threading.Thread(target=self._drive, args=({"messages": [message], "turns": 0},), daemon=True).start()

    def _finish_cancelled(self) -> None:
        self.pending_approval = None
        self.outcome = {"success": False, "verified": False, "cancelled": True, "summary": "اجرا به درخواست شما متوقف شد."}
        self.status = STATUS_DONE
        self._audit("agent.run_cancelled", {})
        self.emit({"type": "done", "outcome": self.outcome})

    def cancel(self) -> None:
        """Stop after the current step (a running tool such as a deploy poll finishes first)."""
        if self.finished:
            raise RunStateError(f"run is already {self.status}")
        assert self._ctx is not None
        self._ctx.cancelled = True
        self.emit({"type": "cancel_requested"})
        if self.status == STATUS_AWAITING:
            self._finish_cancelled()
            with self._cond:
                self._cond.notify_all()

    def steer(self, message: str) -> str:
        """Queue a follow-up chat message for the next agent turn (keeps the run alive)."""
        if self.finished:
            raise RunStateError(f"run is already {self.status}")
        assert self._ctx is not None
        stored = self._ctx.enqueue_note(message)
        self.emit({"type": "user_note", "text": stored})
        self._audit("agent.user_note", {"chars": len(stored)})
        return stored

    def resume(self, *, approved: bool, note: str | None = None) -> None:
        if self.status != STATUS_AWAITING:
            raise RunStateError(f"run is {self.status}, not awaiting approval")
        self.pending_approval = None
        self.status = STATUS_RUNNING
        self.emit({"type": "approval_resolved", "approved": approved})
        threading.Thread(
            target=self._drive, args=(Command(resume={"approved": approved, "note": note}),), daemon=True
        ).start()


class RunRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, AgentRun] = {}
        self._lock = threading.Lock()

    def get(self, run_id: str) -> AgentRun:
        run = self._runs.get(run_id)
        if run is None:
            raise RunNotFound(run_id)
        return run

    def active_for(self, workspace_id: uuid.UUID, project_name: str) -> AgentRun | None:
        with self._lock:
            for run in self._runs.values():
                if run.workspace_id == workspace_id and run.project_name == project_name and not run.finished:
                    return run
        return None

    def create(
        self,
        *,
        workspace_id: uuid.UUID,
        goal: str,
        project_root: str,
        project_name: str,
        conversation_id: str | None = None,
        model: BaseChatModel | None = None,
        liara: LiaraClient | None = None,
        write_guard: WriteGuard | None = None,
        budget: Budget | None = None,
        settings: Settings | None = None,
        start: bool = True,
    ) -> AgentRun:
        root = Path(project_root).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"project folder not found: {project_root}")
        existing = self.active_for(workspace_id, project_name)
        if existing is not None:
            raise RunStateError(f"an agent run is already active for {project_name}: {existing.run_id}")

        cfg = settings or get_settings()
        if model is None or liara is None:
            with session_scope(cfg) as session:
                if model is None:
                    model = LlmService(session, cfg).build_agent_model(workspace_id)
                if liara is None:
                    try:
                        token, base, team = SettingsService(session, cfg).resolve_liara_credentials(workspace_id)
                        liara = LiaraClient(token, base_url=base, team_id=team, timeout=cfg.liara_http_timeout_seconds)
                    except LookupError:
                        liara = None
        if write_guard is None:
            writes_on = cfg.liara_allow_live_writes or live_writes_allowed()
            write_guard = WriteGuard(liara_client=liara if writes_on else None)

        run = AgentRun(
            run_id=f"run-{uuid.uuid4().hex[:12]}",
            workspace_id=workspace_id,
            goal=goal,
            project_root=str(root),
            project_name=project_name,
            conversation_id=conversation_id,
        )
        run._ctx = AgentContext(
            run_id=run.run_id,
            workspace_id=workspace_id,
            project_root=root,
            project_name=project_name,
            liara=liara,
            write_guard=write_guard,
            emit=run.emit,
            audit=run._audit,
            budget=budget or Budget(),
        )
        run._graph = build_agent_graph(run._ctx, model)
        with self._lock:
            self._runs[run.run_id] = run
        run._audit("agent.run_started", {"goal": goal[:500], "project_name": project_name, "project_root": str(root)})
        run.emit({"type": "started", "project_name": project_name, "project_root": str(root), "app_url": run._ctx.app_url})
        if start:
            run.start()
        return run


registry = RunRegistry()

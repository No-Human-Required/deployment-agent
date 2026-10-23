"""Per-run context shared by agent tools (not part of checkpointed graph state)."""

from __future__ import annotations

import re
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.liara_client import LiaraClient
from app.services.write_guard import WriteGuard

EmitFn = Callable[[dict[str, Any]], None]
AuditFn = Callable[[str, dict[str, Any]], None]

MAX_TOOL_OUTPUT_CHARS = 12_000
MAX_PENDING_NOTE_CHARS = 2000
MAX_PENDING_NOTES = 12

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def clip(text: str, limit: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    head = limit * 2 // 3
    tail = limit - head
    return f"{text[:head]}\n…[{len(text) - limit} chars truncated]…\n{text[-tail:]}"


@dataclass
class Budget:
    max_turns: int = 40
    max_redeploys: int = 6
    max_seconds: int = 30 * 60


@dataclass
class AgentContext:
    run_id: str
    workspace_id: uuid.UUID
    project_root: Path
    project_name: str
    liara: LiaraClient | None
    write_guard: WriteGuard
    emit: EmitFn
    audit: AuditFn
    budget: Budget = field(default_factory=Budget)
    started_at: float = field(default_factory=time.monotonic)
    redeploys: int = 0
    last_http: dict[str, Any] | None = None
    checkpoint_ref: str | None = None
    cancelled: bool = False
    sleep: Callable[[float], None] = time.sleep
    http_get: Callable[[str], tuple[int, str, str]] | None = None
    _pending_notes: list[str] = field(default_factory=list, repr=False)
    _notes_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def app_url(self) -> str:
        return f"https://{self.project_name}.liara.run"

    def seconds_left(self) -> float:
        return self.budget.max_seconds - (time.monotonic() - self.started_at)

    def enqueue_note(self, text: str) -> str:
        """Queue a mid-run user message for the next agent turn. Returns the stored text."""
        cleaned = " ".join((text or "").split()).strip()
        if not cleaned:
            raise ValueError("empty note")
        if len(cleaned) > MAX_PENDING_NOTE_CHARS:
            cleaned = cleaned[: MAX_PENDING_NOTE_CHARS - 1] + "…"
        with self._notes_lock:
            if len(self._pending_notes) >= MAX_PENDING_NOTES:
                self._pending_notes.pop(0)
            self._pending_notes.append(cleaned)
        return cleaned

    def drain_notes(self) -> list[str]:
        with self._notes_lock:
            notes = list(self._pending_notes)
            self._pending_notes.clear()
        return notes

    def resolve_path(self, rel: str | None) -> Path:
        """Resolve a path inside the project root; refuse traversal outside it."""
        raw = (rel or ".").strip() or "."
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self.project_root / candidate
        resolved = candidate.resolve()
        root = self.project_root.resolve()
        if resolved != root and root not in resolved.parents:
            raise PermissionError(f"path outside project root: {rel}")
        return resolved

    def rel(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.project_root.resolve())) or "."
        except ValueError:
            return str(path)

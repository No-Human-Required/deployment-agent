"""Shared LangGraph state for the companion orchestrator."""

from __future__ import annotations

import operator
import uuid
from typing import Annotated, Any, TypedDict


class OrchestratorState(TypedDict, total=False):
    workspace_id: str
    case_id: str
    goal: str
    assessment: dict[str, Any]
    plan_id: str
    plan_hash: str
    plan_body: dict[str, Any]
    approval_id: str
    approved: bool
    operation_id: str
    client_request_id: str
    verification: dict[str, Any]
    error: str
    messages: Annotated[list[str], operator.add]


def as_uuid(value: str | uuid.UUID) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))

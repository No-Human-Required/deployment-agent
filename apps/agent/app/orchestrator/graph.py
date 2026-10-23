"""Compiled LangGraph: load → assess → create_plan → await_approval → execute → verify.

HITL: `await_approval` uses langgraph `interrupt()` so sensitive writes pause until
resume. The BFF `approve_plan` + `execute_plan` path also enforces DB approval
independently (fail closed). Model output never calls WriteGuard directly.
"""

from __future__ import annotations

from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.orchestrator.state import OrchestratorState, as_uuid
from app.services.orchestrator import (
    ApprovalExpiredError,
    ApprovalRequiredError,
    OrchestratorError,
    OrchestratorService,
    SchemaValidationError,
)


def build_orchestrator_graph(
    service: OrchestratorService,
    *,
    checkpointer: Any | None = None,
):
    """Build and compile the companion graph (MemorySaver by default for tests)."""

    def load_case(state: OrchestratorState) -> dict[str, Any]:
        workspace_id = as_uuid(state["workspace_id"])
        case_id = state.get("case_id")
        case = service.ensure_case(
            workspace_id=workspace_id,
            case_id=as_uuid(case_id) if case_id else None,
            goal=state.get("goal") or "unspecified goal",
        )
        return {
            "case_id": str(case.id),
            "goal": case.goal,
            "messages": [f"loaded_case:{case.id}"],
        }

    def assess(state: OrchestratorState) -> dict[str, Any]:
        assessment = service.assess_readiness(
            workspace_id=as_uuid(state["workspace_id"]),
            case_id=as_uuid(state["case_id"]),
        )
        return {
            "assessment": assessment.model_dump(mode="json"),
            "messages": ["assessed"],
        }

    def create_plan(state: OrchestratorState) -> dict[str, Any]:
        try:
            plan, validated = service.create_plan(
                workspace_id=as_uuid(state["workspace_id"]),
                case_id=as_uuid(state["case_id"]),
                plan_draft=state.get("plan_body"),
                use_llm=False,
            )
        except SchemaValidationError as exc:
            return {"error": str(exc), "messages": ["create_plan_schema_invalid"]}
        return {
            "plan_id": str(plan.id),
            "plan_hash": plan.content_hash or "",
            "plan_body": validated.model_dump(mode="json"),
            "messages": [f"plan_created:{plan.id}"],
        }

    def await_approval(
        state: OrchestratorState,
    ) -> Command[Literal["execute_stub", "__end__"]]:
        if state.get("error"):
            return Command(goto=END, update={"messages": ["skipped_approval_due_to_error"]})

        # Pause for human decision. Resume value: {"approved": bool, "approval_id"?: str}
        decision = interrupt(
            {
                "type": "approve_plan",
                "plan_id": state.get("plan_id"),
                "plan_hash": state.get("plan_hash"),
                "plan_body": state.get("plan_body"),
            }
        )
        approved = bool(decision.get("approved")) if isinstance(decision, dict) else bool(decision)
        update: dict[str, Any] = {
            "approved": approved,
            "messages": ["approval_resumed"],
        }
        if isinstance(decision, dict) and decision.get("approval_id"):
            update["approval_id"] = str(decision["approval_id"])
        if not approved:
            update["error"] = "approval_rejected"
            return Command(goto=END, update=update)
        return Command(goto="execute_stub", update=update)

    def execute_stub(state: OrchestratorState) -> dict[str, Any]:
        workspace_id = as_uuid(state["workspace_id"])
        plan_id = as_uuid(state["plan_id"])
        client_request_id = state.get("client_request_id") or f"graph-{plan_id}"
        try:
            # Prefer DB approval gate (explicit approve_plan). If graph resume only,
            # create a short-lived approval so execute_plan fail-closed still holds.
            try:
                service.get_valid_approval(workspace_id=workspace_id, plan_id=plan_id)
            except (ApprovalRequiredError, ApprovalExpiredError):
                if state.get("approved"):
                    service.approve_plan(workspace_id=workspace_id, plan_id=plan_id)
                else:
                    raise
            op = service.execute_plan(
                workspace_id=workspace_id,
                plan_id=plan_id,
                client_request_id=client_request_id,
            )
        except OrchestratorError as exc:
            return {"error": str(exc), "messages": [f"execute_blocked:{exc.code}"]}
        return {
            "operation_id": str(op.id),
            "messages": [f"execute_stub:{op.id}"],
        }

    def verify_stub(state: OrchestratorState) -> dict[str, Any]:
        if state.get("error") or not state.get("operation_id"):
            return {"messages": ["verify_skipped"]}
        op = service.verify_result(
            workspace_id=as_uuid(state["workspace_id"]),
            operation_id=as_uuid(state["operation_id"]),
        )
        return {
            "verification": {"state": op.state, "operation_id": str(op.id)},
            "messages": ["verified_stub"],
        }

    graph = StateGraph(OrchestratorState)
    graph.add_node("load_case", load_case)
    graph.add_node("assess", assess)
    graph.add_node("create_plan", create_plan)
    graph.add_node("await_approval", await_approval)
    graph.add_node("execute_stub", execute_stub)
    graph.add_node("verify_stub", verify_stub)

    graph.add_edge(START, "load_case")
    graph.add_edge("load_case", "assess")
    graph.add_edge("assess", "create_plan")
    graph.add_edge("create_plan", "await_approval")
    # await_approval routes via Command
    graph.add_edge("execute_stub", "verify_stub")
    graph.add_edge("verify_stub", END)

    saver = checkpointer if checkpointer is not None else MemorySaver()
    return graph.compile(checkpointer=saver)


def get_compiled_graph(service: OrchestratorService, *, checkpointer: Any | None = None):
    """Compile a graph bound to the given service (not a process-wide singleton)."""
    return build_orchestrator_graph(service, checkpointer=checkpointer)

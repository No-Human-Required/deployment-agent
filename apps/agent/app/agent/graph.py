"""LangGraph DevOps agent: agent ⇄ tools loop with approval and verification gates.

    START → agent ─┬─ tool calls ──────────────→ tools → agent
                   ├─ gated tool calls ────────→ approval_gate (interrupt) → tools | agent
                   ├─ finish ──────────────────→ verify_gate → END | agent (rejected)
                   ├─ no tool call ────────────→ nudge → agent
                   └─ budget exhausted ────────→ budget_exhausted → END

Tools run sequentially (writes must not race). Tool errors become ToolMessages so the
model can recover. ``finish(success=True)`` is only accepted after an OK http_check on
the app URL — the model cannot declare victory from a release id.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

from app.agent.context import AgentContext, clip
from app.agent.prompts import build_system_prompt
from app.agent.tools import FINISH_TOOL, GATED_TOOLS, build_tools
from app.services.troubleshoot import sanitize_log_line

MAX_NUDGES = 2


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    turns: int
    nudges: int
    outcome: dict[str, Any]


def message_text(message: AnyMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
    return "".join(parts)


def _last_ai(state: AgentState) -> AIMessage | None:
    for message in reversed(state.get("messages") or []):
        if isinstance(message, AIMessage):
            return message
    return None


def _skip_messages(ai: AIMessage, reason: str, *, except_ids: set[str] | None = None) -> list[ToolMessage]:
    return [
        ToolMessage(content=reason, tool_call_id=call["id"], name=call["name"], status="error")
        for call in ai.tool_calls
        if call["id"] not in (except_ids or set())
    ]


def build_agent_graph(
    ctx: AgentContext,
    model: BaseChatModel,
    *,
    tools: list[BaseTool] | None = None,
    checkpointer: Any | None = None,
):
    tool_list = tools if tools is not None else build_tools(ctx)
    by_name = {t.name: t for t in tool_list}
    bound = model.bind_tools(tool_list)
    system_prompt = build_system_prompt(ctx)

    def _budget_left(state: AgentState) -> bool:
        return state.get("turns", 0) < ctx.budget.max_turns and ctx.seconds_left() > 0

    def agent(state: AgentState) -> dict[str, Any]:
        turns = state.get("turns", 0)
        # Mid-run chat: user notes arrive from another thread; fold them in before the next model call.
        note_msgs = [
            HumanMessage(
                "User message while you were working — treat it as guidance for the current goal "
                f"(do not restart from scratch unless they ask):\n{note}"
            )
            for note in ctx.drain_notes()
        ]
        status = (
            f"\n\n[status] turns used {turns}/{ctx.budget.max_turns}, deploys {ctx.redeploys}/"
            f"{ctx.budget.max_redeploys}, minutes left {max(0, int(ctx.seconds_left() // 60))}, "
            f"last http_check: {ctx.last_http or 'none yet'}"
        )
        response = bound.invoke(
            [SystemMessage(system_prompt + status), *state.get("messages", []), *note_msgs]
        )
        text = message_text(response).strip()
        if text:
            ctx.emit({"type": "thought", "text": text})
        return {"messages": [*note_msgs, response], "turns": turns + 1}

    def route_after_agent(
        state: AgentState,
    ) -> Literal["tools", "approval_gate", "verify_gate", "nudge", "budget_exhausted"]:
        ai = _last_ai(state)
        calls = ai.tool_calls if ai else []
        if any(c["name"] == FINISH_TOOL for c in calls):
            return "verify_gate"
        if not _budget_left(state):
            return "budget_exhausted"
        if not calls:
            return "nudge" if state.get("nudges", 0) < MAX_NUDGES else "budget_exhausted"
        if any(c["name"] in GATED_TOOLS for c in calls):
            return "approval_gate"
        return "tools"

    def tools(state: AgentState) -> dict[str, Any]:
        ai = _last_ai(state)
        results: list[ToolMessage] = []
        for call in ai.tool_calls if ai else []:
            name, args = call["name"], call.get("args") or {}
            ctx.emit({"type": "tool_call", "id": call["id"], "name": name, "args": _safe_args(args)})
            tool = by_name.get(name)
            if tool is None:
                content, status = f"Error: unknown tool {name}", "error"
            else:
                try:
                    content, status = str(tool.invoke(args)), "success"
                except Exception as exc:  # noqa: BLE001 — surfaced to the model as an observation
                    content, status = f"Error: {type(exc).__name__}: {exc}", "error"
            preview, _ = sanitize_log_line(content[:1500])
            ctx.emit({"type": "tool_result", "id": call["id"], "name": name, "ok": status == "success", "preview": preview})
            results.append(ToolMessage(content=clip(content), tool_call_id=call["id"], name=name, status=status))
        return {"messages": results}

    def approval_gate(state: AgentState) -> Command[Literal["tools", "agent"]]:
        ai = _last_ai(state)
        gated = [
            {"id": c["id"], "name": c["name"], "args": _safe_args(c.get("args") or {})}
            for c in (ai.tool_calls if ai else [])
            if c["name"] in GATED_TOOLS
        ]
        decision = interrupt({"type": "approval_required", "calls": gated})
        approved = bool(decision.get("approved")) if isinstance(decision, dict) else bool(decision)
        ctx.audit("agent.approval", {"approved": approved, "calls": [g["name"] for g in gated]})
        if approved:
            return Command(goto="tools")
        note = decision.get("note") if isinstance(decision, dict) else None
        reason = "The user declined this action." + (f" User note: {note}" if note else "")
        return Command(goto="agent", update={"messages": _skip_messages(ai, reason)})

    def verify_gate(state: AgentState) -> Command[Literal["agent", "__end__"]]:
        ai = _last_ai(state)
        finish_call = next(c for c in ai.tool_calls if c["name"] == FINISH_TOOL)
        args = finish_call.get("args") or {}
        wants_success = bool(args.get("success"))
        summary = str(args.get("summary") or message_text(ai)).strip()
        verified = bool(ctx.last_http and ctx.last_http.get("ok"))
        others = _skip_messages(ai, "Not executed: finish was called in the same turn.", except_ids={finish_call["id"]})
        if wants_success and not verified and _budget_left(state):
            rejection = (
                f"REJECTED: success requires an OK http_check on {ctx.app_url}. Last check: "
                f"{ctx.last_http or 'none'}. Keep working: check releases, liara_runtime_logs, fix, redeploy, verify."
            )
            ctx.emit({"type": "verify_rejected", "last_http": ctx.last_http})
            return Command(
                goto="agent",
                update={"messages": [*others, ToolMessage(content=rejection, tool_call_id=finish_call["id"], name=FINISH_TOOL, status="error")]},
            )
        outcome = {
            "success": wants_success and verified,
            "verified": verified,
            "summary": summary,
            "url": ctx.app_url,
            "last_http": ctx.last_http,
        }
        return Command(
            goto=END,
            update={
                "messages": [*others, ToolMessage(content="finished", tool_call_id=finish_call["id"], name=FINISH_TOOL)],
                "outcome": outcome,
            },
        )

    def nudge(state: AgentState) -> dict[str, Any]:
        return {
            "nudges": state.get("nudges", 0) + 1,
            "messages": [
                HumanMessage(
                    "Continue autonomously with tools. If the app is verified working (http_check OK) "
                    "or you are truly blocked, call finish(success, summary)."
                )
            ],
        }

    def budget_exhausted(state: AgentState) -> dict[str, Any]:
        ai = _last_ai(state)
        closing = _skip_messages(ai, "Not executed: run budget exhausted.") if ai and ai.tool_calls else []
        ask = HumanMessage(
            "The run budget is exhausted. Without calling tools, write the final Persian summary for the user: "
            "what you found (with evidence), what you changed, the current state of the URL, and the exact next step."
        )
        try:
            final = model.invoke([SystemMessage(system_prompt), *state.get("messages", []), *closing, ask])
            summary = message_text(final).strip()
        except Exception:  # noqa: BLE001 — fall back to the last thing the model said
            summary = message_text(ai).strip() if ai else ""
        verified = bool(ctx.last_http and ctx.last_http.get("ok"))
        return {
            "messages": closing,
            "outcome": {
                "success": False,
                "verified": verified,
                "summary": summary or "بودجه‌ی اجرا تمام شد و برنامه هنوز تأیید نشده است.",
                "url": ctx.app_url,
                "last_http": ctx.last_http,
                "budget_exhausted": True,
            },
        }

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent)
    graph.add_node("tools", tools)
    graph.add_node("approval_gate", approval_gate)
    graph.add_node("verify_gate", verify_gate)
    graph.add_node("nudge", nudge)
    graph.add_node("budget_exhausted", budget_exhausted)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        ["tools", "approval_gate", "verify_gate", "nudge", "budget_exhausted"],
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("nudge", "agent")
    graph.add_edge("budget_exhausted", END)

    return graph.compile(checkpointer=checkpointer if checkpointer is not None else MemorySaver())


def recursion_limit_for(ctx: AgentContext) -> int:
    return ctx.budget.max_turns * 3 + 20


def _safe_args(args: dict[str, Any]) -> dict[str, Any]:
    """Shorten bulky args (file contents, env values) for the activity feed."""
    out: dict[str, Any] = {}
    for key, value in args.items():
        if key == "variables" and isinstance(value, dict):
            out[key] = sorted(value.keys())
        elif isinstance(value, str) and len(value) > 300:
            out[key] = value[:300] + "…"
        else:
            out[key] = value
    return out

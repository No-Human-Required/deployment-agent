"""DevOps agent loop — scripted fake model + fake Liara (no network, no DB)."""

from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.types import Command

from app.agent.context import AgentContext, Budget
from app.agent.graph import build_agent_graph, recursion_limit_for
from app.agent.skills import load_skills
from app.agent.tools.files import _validate_command
from app.agent.tools.liara import collect_archive_files, liara_json_release_fields, redact_env_value
from app.services.write_guard import WriteGuard

LIARA_502 = "<html><head><title>Liara | Application Error</title></head><body>502</body></html>"
REAL_PAGE = "<html><head><title>Mail Inbox</title></head><body><div id=root>Inbox</div></body></html>"


class ScriptedModel(BaseChatModel):
    """Returns pre-scripted AI messages in order; records what it was shown."""

    script: list[AIMessage]
    seen: list[list[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> ScriptedModel:  # noqa: ARG002
        return self

    def _generate(self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        self.seen.append(list(messages))
        message = self.script.pop(0) if self.script else AIMessage(content="(script exhausted)")
        return ChatResult(generations=[ChatGeneration(message=message)])


def call(name: str, args: dict[str, Any] | None = None, *, text: str = "") -> AIMessage:
    return AIMessage(
        content=text,
        tool_calls=[{"id": f"call-{uuid.uuid4().hex[:8]}", "name": name, "args": args or {}, "type": "tool_call"}],
    )


class FakeLiara:
    """Minimal LiaraClient stand-in: releases become READY immediately."""

    def __init__(self) -> None:
        self.releases: list[dict[str, Any]] = []
        self.envs = [{"key": "DATABASE_URL", "value": "postgres://root:s3cret@db:5432/wrong"}]
        self.logs = [{"ts": "1", "stream": "stderr", "message": "Error: listen EADDRNOTAVAIL 127.0.0.1", "release_id": "r0"}]

    def get_project(self, name: str) -> dict[str, Any]:
        return {"name": name, "type": "node", "status": "ACTIVE", "envs": self.envs, "network": {"name": "net"}}

    def project_envs(self, name: str) -> list[dict[str, Any]]:  # noqa: ARG002
        return self.envs

    def list_releases(self, name: str) -> dict[str, Any]:  # noqa: ARG002
        return {"releases": list(reversed(self.releases)), "currentRelease": self.releases[-1]["_id"] if self.releases else None}

    def get_runtime_logs(self, name: str, *, since: int | None = None) -> list[dict[str, Any]]:  # noqa: ARG002
        return self.logs

    def get_build_logs(self, release_id: str) -> dict[str, Any]:
        return {"state": "FAILED", "lines": [{"stream": "STDOUT", "line": f"build of {release_id} failed"}]}


class FakeProviderWrite:
    def __init__(self, liara: FakeLiara) -> None:
        self.liara = liara
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, *, tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((tool_id, payload))
        if tool_id == "sources":
            return {"sourceID": "src-1"}
        if tool_id == "releases":
            rid = f"r{len(self.liara.releases) + 1}"
            self.liara.releases.append({"_id": rid, "type": "DEPLOY", "state": "READY", "port": payload["port"]})
            return {"releaseID": rid}
        if tool_id == "update_envs":
            self.liara.envs = payload["variables"]
            return {"message": "ok"}
        return {"ok": True}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"start": "node server.js"}}))
    (tmp_path / "server.js").write_text("app.listen(3000, '127.0.0.1');\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    return tmp_path


def make_ctx(project: Path, http_bodies: list[tuple[int, str]], *, budget: Budget | None = None):
    liara = FakeLiara()
    provider = FakeProviderWrite(liara)
    events: list[dict[str, Any]] = []
    audits: list[tuple[str, dict[str, Any]]] = []
    bodies = list(http_bodies)

    def http_get(url: str) -> tuple[int, str, str]:  # noqa: ARG001
        status, body = bodies.pop(0) if len(bodies) > 1 else bodies[0]
        return status, "text/html", body

    ctx = AgentContext(
        run_id="test-run",
        workspace_id=uuid.uuid4(),
        project_root=project,
        project_name="demo-app",
        liara=liara,  # type: ignore[arg-type]
        write_guard=WriteGuard(provider_write=provider),
        emit=events.append,
        audit=lambda kind, payload: audits.append((kind, payload)),
        budget=budget or Budget(),
        sleep=lambda _s: None,
        http_get=http_get,
    )
    return ctx, liara, provider, events, audits


def run_graph(ctx: AgentContext, model: ScriptedModel, graph_input: Any = None):
    graph = build_agent_graph(ctx, model)
    config = {"configurable": {"thread_id": ctx.run_id}, "recursion_limit": recursion_limit_for(ctx)}
    result = graph.invoke(graph_input or {"messages": [("user", "deploy it")], "turns": 0}, config)
    return graph, config, result


def test_502_loop_reads_logs_fixes_bind_redeploys_and_verifies(project: Path) -> None:
    ctx, _liara, provider, events, audits = make_ctx(project, [(502, LIARA_502), (200, REAL_PAGE)])
    model = ScriptedModel(
        script=[
            call("http_check", text="ابتدا وضعیت فعلی را بررسی می‌کنم."),
            call("liara_runtime_logs"),
            call("edit_file", {"path": "server.js", "old_string": "'127.0.0.1'", "new_string": "'0.0.0.0'"}),
            call("liara_deploy", {"port": 3000}),
            call("http_check", {"wait_seconds": 60}),
            call("finish", {"success": True, "summary": "برنامه روی 0.0.0.0 اجرا شد و بالا است."}),
        ]
    )
    _, _, result = run_graph(ctx, model)

    outcome = result["outcome"]
    assert outcome["success"] is True and outcome["verified"] is True
    assert "0.0.0.0" in (project / "server.js").read_text()
    assert [c[0] for c in provider.calls] == ["sources", "releases"]
    assert ctx.redeploys == 1
    log_result = next(m for m in result["messages"] if isinstance(m, ToolMessage) and m.name == "liara_runtime_logs")
    assert "EADDRNOTAVAIL" in log_result.content
    kinds = {e["type"] for e in events}
    assert {"thought", "tool_call", "tool_result", "diff", "checkpoint", "deploy", "http_check"} <= kinds
    checkpoint = next(e for e in events if e["type"] == "checkpoint")
    assert checkpoint["ref"] == "refs/liara-agent/test-run"
    assert any(kind == "agent.file_edit" for kind, _ in audits)


def test_finish_success_rejected_until_http_check_passes(project: Path) -> None:
    ctx, *_ , events, _ = make_ctx(project, [(502, LIARA_502)])
    model = ScriptedModel(
        script=[
            call("finish", {"success": True, "summary": "release ثبت شد"}),
            call("http_check"),
            call("finish", {"success": False, "summary": "هنوز 502 است؛ لاگ‌ها را ببینید."}),
        ]
    )
    _, _, result = run_graph(ctx, model)

    rejection = next(m for m in result["messages"] if isinstance(m, ToolMessage) and m.name == "finish")
    assert rejection.content.startswith("REJECTED")
    assert any(e["type"] == "verify_rejected" for e in events)
    assert result["outcome"]["success"] is False
    assert result["outcome"]["verified"] is False


def test_gated_tool_interrupts_and_decline_reaches_model(project: Path) -> None:
    ctx, _liara, provider, _events, audits = make_ctx(project, [(200, REAL_PAGE)])
    model = ScriptedModel(
        script=[
            call("liara_create_database", {"hostname": "demo-db"}),
            call("finish", {"success": False, "summary": "کاربر ساخت دیتابیس را رد کرد."}),
        ]
    )
    graph, config, result = run_graph(ctx, model)

    assert "__interrupt__" in result
    payload = result["__interrupt__"][0].value
    assert payload["type"] == "approval_required"
    assert payload["calls"][0]["name"] == "liara_create_database"
    assert provider.calls == []

    resumed = graph.invoke(Command(resume={"approved": False, "note": "گران است"}), config)
    declined = next(m for m in resumed["messages"] if isinstance(m, ToolMessage) and m.name == "liara_create_database")
    assert "declined" in declined.content and "گران است" in declined.content
    assert provider.calls == []
    assert resumed["outcome"]["success"] is False
    assert ("agent.approval", {"approved": False, "calls": ["liara_create_database"]}) in audits


def test_gated_tool_runs_after_approval(project: Path) -> None:
    ctx, _liara, provider, *_ = make_ctx(project, [(200, REAL_PAGE)])
    model = ScriptedModel(
        script=[
            call("liara_create_disk", {"name": "data", "size_gb": 1}),
            call("finish", {"success": False, "summary": "دیسک ساخته شد."}),
        ]
    )
    graph, config, _ = run_graph(ctx, model)
    graph.invoke(Command(resume={"approved": True}), config)
    assert provider.calls[0][0] == "create_disk"


def test_pending_user_notes_reach_the_model(project: Path) -> None:
    ctx, *_ = make_ctx(project, [(200, REAL_PAGE)])
    stored = ctx.enqueue_note("بخاطر شبکه خصوصی نیست؟")
    assert "شبکه خصوصی" in stored
    model = ScriptedModel(
        script=[call("finish", {"success": False, "summary": "checking private network"})],
    )
    run_graph(ctx, model)
    joined = "\n".join(
        m.content if isinstance(m.content, str) else "" for batch in model.seen for m in batch
    )
    assert "شبکه خصوصی" in joined
    assert ctx.drain_notes() == []


def test_budget_exhaustion_ends_with_honest_failure(project: Path) -> None:
    ctx, *_ = make_ctx(project, [(502, LIARA_502)], budget=Budget(max_turns=3))
    model = ScriptedModel(
        script=[
            call("http_check"),
            call("liara_runtime_logs"),
            call("liara_list_releases"),
            AIMessage(content="خلاصه: برنامه هنوز 502 می‌دهد؛ پورت را بررسی کنید."),
        ]
    )
    _, _, result = run_graph(ctx, model)
    outcome = result["outcome"]
    assert outcome["success"] is False and outcome["budget_exhausted"] is True
    assert "502" in outcome["summary"]
    # Every tool call got an answer, so the transcript stays valid for the provider API.
    ai_ids = {c["id"] for m in result["messages"] if isinstance(m, AIMessage) for c in m.tool_calls}
    tool_ids = {m.tool_call_id for m in result["messages"] if isinstance(m, ToolMessage)}
    assert ai_ids == tool_ids


def test_tool_errors_are_returned_to_model(project: Path) -> None:
    ctx, *_ = make_ctx(project, [(200, REAL_PAGE)])
    model = ScriptedModel(
        script=[
            call("read_file", {"path": "../../etc/passwd"}),
            call("run_command", {"command": "rm -rf /"}),
            call("finish", {"success": False, "summary": "done"}),
        ]
    )
    _, _, result = run_graph(ctx, model)
    errors = [m for m in result["messages"] if isinstance(m, ToolMessage) and m.status == "error" and m.name != "finish"]
    assert len(errors) == 2
    assert "outside project root" in errors[0].content
    assert "not allowed" in errors[1].content


def test_set_envs_merges_and_redacts(project: Path) -> None:
    ctx, liara, provider, events, _ = make_ctx(project, [(200, REAL_PAGE)])
    model = ScriptedModel(
        script=[
            call("liara_set_envs", {"variables": {"NODE_ENV": "production"}, "generate_secrets": ["JWT_SECRET"]}),
            call("finish", {"success": False, "summary": "envs"}),
        ]
    )
    run_graph(ctx, model)
    keys = {v["key"] for v in liara.envs}
    assert keys == {"DATABASE_URL", "NODE_ENV", "JWT_SECRET"}
    env_event = next(e for e in events if e["type"] == "envs")
    assert "JWT_SECRET(generated)" in env_event["changed"]
    shown = next(e for e in events if e["type"] == "tool_call" and e["name"] == "liara_set_envs")
    assert shown["args"]["variables"] == ["NODE_ENV"]


def test_redaction_and_command_allowlist() -> None:
    assert redact_env_value("DATABASE_URL", "postgres://root:pw@h:5432/db") == "postgres://root:***@h:5432/db"
    assert redact_env_value("SMTP_PASSWORD", "abc").startswith("***set")
    assert redact_env_value("NODE_ENV", "production") == "production"
    _validate_command(["npm", "run", "build"])
    _validate_command(["npx", "prisma", "generate"])
    for bad in (["npx", "prisma", "migrate", "reset"], ["bash", "-c", "x"], ["npm", "publish"], ["npm", "run", "build", "&&", "rm"]):
        with pytest.raises(PermissionError):
            _validate_command(bad)


def test_skills_have_frontmatter() -> None:
    skills = load_skills()
    assert {"devops-deploy-loop", "liara-paas-node", "liara-502-troubleshooting", "liara-dbaas-and-envs", "liara-domains-ssl", "liara-docs-map"} <= set(skills)
    assert all(s.description and len(s.body) > 200 for s in skills.values())


def test_archive_follows_liara_cli_ignore_rules(tmp_path: Path) -> None:
    files = {
        "package.json": "{}",
        "package-lock.json": "{}",
        ".gitignore": "dist\nnode_modules\n",
        ".liaraignore": "package-lock.json\n*.log\n",
        ".env": "SECRET=1",
        ".env.example": "SECRET=",
        "liara.json": "{}",
        "debug.log": "x",
        "dist/main.js": "root dist is kept: .liaraignore replaces .gitignore",
        "apps/web/.gitignore": "dist/\n!keep.txt\n",
        "apps/web/dist/index.html": "<html>",
        "apps/web/src/main.tsx": "x",
        "node_modules/a/index.js": "x",
        ".git/HEAD": "ref",
    }
    for rel, body in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(body)

    rels = {p.relative_to(tmp_path).as_posix() for p in collect_archive_files(tmp_path)}
    assert rels == {
        "package.json", ".gitignore", ".liaraignore", ".env.example", "dist/main.js",
        "apps/web/.gitignore", "apps/web/src/main.tsx",
    }

    with_build = {p.relative_to(tmp_path).as_posix() for p in collect_archive_files(tmp_path, include_build_output=True)}
    assert "apps/web/dist/index.html" in with_build
    assert ".env" not in with_build


def test_liara_json_fields_are_sent_like_cli(tmp_path: Path) -> None:
    (tmp_path / "liara.json").write_text(json.dumps({
        "port": 8080,
        "node": {"version": "22", "mirror": True},
        "build": {"location": "germany", "cache": False, "junk": 1},
        "healthCheck": {"command": "CMD curl --fail http://localhost:8080/ || exit 1"},
    }))
    fields = liara_json_release_fields(tmp_path, "node")
    assert fields["port"] == 8080
    assert fields["platformConfig"] == {"version": "22", "mirror": True}
    assert fields["build"] == {"location": "germany", "cache": False}
    assert fields["healthCheck"]["command"][0] == "CMD"
    assert liara_json_release_fields(tmp_path / "missing", "node") == {}

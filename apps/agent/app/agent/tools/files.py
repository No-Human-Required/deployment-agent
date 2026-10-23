"""Project file tools — confined to the project root, git checkpoint before first edit."""

from __future__ import annotations

import difflib
import fnmatch
import os
import re
import shlex
import subprocess
from pathlib import Path

from langchain_core.tools import BaseTool, tool

from app.agent.context import AgentContext, clip, strip_ansi
from app.services.patch import scrub_env

_SKIP_DIRS = frozenset(
    {".git", "node_modules", ".next", "dist", "build", "coverage", ".turbo", ".cache", ".venv", "__pycache__"}
)
_SECRET_FILE_RE = re.compile(r"(^|/)\.env(\.[\w-]+)?$")
_SECRET_FILE_ALLOW = re.compile(r"\.env\.(example|sample|template)$")

_NPM_SUBCOMMANDS = frozenset({"install", "i", "ci", "run", "run-script", "ls", "view", "why", "--version", "-v"})
_NPX_BINARIES = frozenset({"tsc", "nest", "prisma", "next", "vite", "eslint"})
_PRISMA_SUBCOMMANDS = frozenset({"generate", "validate", "format", "--version"})
_GIT_SUBCOMMANDS = frozenset({"status", "diff", "log", "show"})
_COMMAND_TIMEOUT = 600


def _is_secret_file(rel: str) -> bool:
    return bool(_SECRET_FILE_RE.search(rel)) and not _SECRET_FILE_ALLOW.search(rel)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=30, check=False
    )


def ensure_checkpoint(ctx: AgentContext) -> None:
    """Record the pre-edit state under refs/liara-agent/<run_id> without touching the worktree."""
    if ctx.checkpoint_ref is not None:
        return
    root = ctx.project_root
    if _git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        ctx.checkpoint_ref = ""
        ctx.emit({"type": "checkpoint", "ref": None, "note": "not a git repository — no checkpoint"})
        return
    stash = _git(root, "stash", "create", "liara-agent checkpoint").stdout.strip()
    sha = stash or _git(root, "rev-parse", "HEAD").stdout.strip()
    ref = f"refs/liara-agent/{ctx.run_id}"
    if sha:
        _git(root, "update-ref", ref, sha)
    ctx.checkpoint_ref = ref if sha else ""
    ctx.emit(
        {
            "type": "checkpoint",
            "ref": ref if sha else None,
            "restore": f"git checkout {ref} -- <file>" if sha else None,
        }
    )


def _validate_command(argv: list[str]) -> None:
    if not argv:
        raise PermissionError("empty command")
    exe, rest = argv[0], argv[1:]
    if any(tok in {"&&", "||", ";", "|", ">", ">>", "<"} for tok in argv):
        raise PermissionError("shell operators are not allowed; run one command at a time")
    if exe in ("npm", "pnpm", "yarn"):
        sub = rest[0] if rest else "install"
        allowed = _NPM_SUBCOMMANDS | ({"build"} if exe != "npm" else frozenset())
        if sub not in allowed:
            raise PermissionError(f"{exe} {sub} is not allowed (allowed: install, ci, run <script>, ls, view)")
        return
    if exe == "npx":
        args = [a for a in rest if not a.startswith("-")]
        binary = args[0] if args else ""
        if binary not in _NPX_BINARIES:
            raise PermissionError(f"npx {binary} is not allowed (allowed: {', '.join(sorted(_NPX_BINARIES))})")
        if binary == "prisma" and (len(args) < 2 or args[1] not in _PRISMA_SUBCOMMANDS):
            raise PermissionError("only prisma generate/validate/format are allowed")
        return
    if exe == "node":
        if rest not in (["--version"], ["-v"]):
            raise PermissionError("only node --version is allowed")
        return
    if exe == "git":
        if not rest or rest[0] not in _GIT_SUBCOMMANDS:
            raise PermissionError("only git status/diff/log/show are allowed")
        return
    raise PermissionError(f"command '{exe}' is not allowed")


def build_file_tools(ctx: AgentContext) -> list[BaseTool]:
    @tool
    def list_dir(path: str = ".", depth: int = 2) -> str:
        """List files and folders under a project path (skips node_modules, .git, build output)."""
        base = ctx.resolve_path(path)
        if not base.is_dir():
            return f"not a directory: {path}"
        lines: list[str] = []
        max_depth = max(1, min(depth, 4))

        def walk(directory: Path, level: int) -> None:
            try:
                entries = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name))
            except OSError:
                return
            for entry in entries:
                if entry.name in _SKIP_DIRS or entry.name == ".DS_Store":
                    continue
                indent = "  " * level
                if entry.is_dir():
                    lines.append(f"{indent}{entry.name}/")
                    if level + 1 < max_depth:
                        walk(entry, level + 1)
                else:
                    lines.append(f"{indent}{entry.name}")
                if len(lines) > 400:
                    return

        walk(base, 0)
        return clip("\n".join(lines) or "(empty)")

    @tool
    def read_file(path: str, offset: int = 1, limit: int = 400) -> str:
        """Read a text file in the project (1-based line offset). .env files are redacted to keys only."""
        target = ctx.resolve_path(path)
        if not target.is_file():
            return f"file not found: {path}"
        text = target.read_text(encoding="utf-8", errors="replace")
        rel = ctx.rel(target)
        if _is_secret_file(rel):
            keys = [ln.split("=", 1)[0] for ln in text.splitlines() if "=" in ln and not ln.lstrip().startswith("#")]
            return f"{rel} is a secret file; keys only:\n" + "\n".join(keys)
        lines = text.splitlines()
        start = max(1, offset)
        chunk = lines[start - 1 : start - 1 + max(1, min(limit, 2000))]
        numbered = "\n".join(f"{start + i:>5}| {ln}" for i, ln in enumerate(chunk))
        more = f"\n…({len(lines) - (start - 1 + len(chunk))} more lines)" if start - 1 + len(chunk) < len(lines) else ""
        return clip(f"{rel} ({len(lines)} lines)\n{numbered}{more}")

    @tool
    def grep(pattern: str, path: str = ".", glob: str | None = None) -> str:
        """Search project files with a regex (case-insensitive). glob filters file names, e.g. "*.ts"."""
        base = ctx.resolve_path(path)
        regex = re.compile(pattern, re.IGNORECASE)
        hits: list[str] = []
        files = [base] if base.is_file() else base.rglob("*")
        for file in files:
            if len(hits) >= 120:
                break
            if not file.is_file() or any(part in _SKIP_DIRS for part in file.parts):
                continue
            rel = ctx.rel(file)
            if glob and not fnmatch.fnmatch(file.name, glob):
                continue
            if _is_secret_file(rel) or file.stat().st_size > 1_000_000:
                continue
            try:
                for i, line in enumerate(file.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if regex.search(line):
                        hits.append(f"{rel}:{i}: {line.strip()[:200]}")
                        if len(hits) >= 120:
                            break
            except OSError:
                continue
        return clip("\n".join(hits) or "(no matches)")

    def _write(target: Path, new_text: str) -> str:
        rel = ctx.rel(target)
        if _is_secret_file(rel):
            raise PermissionError("refusing to write .env files; set envs on Liara with liara_set_envs")
        ensure_checkpoint(ctx)
        old_text = target.read_text(encoding="utf-8") if target.is_file() else ""
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_text, encoding="utf-8")
        diff = "".join(
            difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
        )
        ctx.emit({"type": "diff", "path": rel, "diff": clip(diff, 6000)})
        ctx.audit("agent.file_edit", {"path": rel, "checkpoint": ctx.checkpoint_ref})
        return diff

    @tool
    def edit_file(path: str, old_string: str, new_string: str) -> str:
        """Replace one exact occurrence of old_string with new_string in a project file.

        old_string must match exactly (including indentation) and be unique in the file.
        """
        target = ctx.resolve_path(path)
        if not target.is_file():
            return f"file not found: {path} (use write_file to create it)"
        text = target.read_text(encoding="utf-8")
        count = text.count(old_string)
        if count == 0:
            return "old_string not found; read_file again and copy the exact text"
        if count > 1:
            return f"old_string occurs {count} times; include more surrounding lines to make it unique"
        diff = _write(target, text.replace(old_string, new_string, 1))
        return clip(f"edited {ctx.rel(target)}\n{diff}", 4000)

    @tool
    def write_file(path: str, content: str) -> str:
        """Create or overwrite a project file with the full content (e.g. liara.json)."""
        target = ctx.resolve_path(path)
        diff = _write(target, content)
        return clip(f"wrote {ctx.rel(target)}\n{diff}", 4000)

    @tool
    def run_command(command: str, cwd: str = ".") -> str:
        """Run one allowlisted build command locally to prove the project builds before deploying.

        Allowed: npm/pnpm/yarn install|ci|run <script>|ls|view, npx tsc|nest|prisma generate|next|vite,
        node --version, git status|diff|log|show. No shell operators. Timeout 10 minutes.
        """
        argv = shlex.split(command)
        _validate_command(argv)
        workdir = ctx.resolve_path(cwd)
        ctx.emit({"type": "command", "command": command, "cwd": ctx.rel(workdir)})
        env = scrub_env(dict(os.environ))
        env.setdefault("CI", "1")
        try:
            proc = subprocess.run(
                argv, cwd=str(workdir), env=env, capture_output=True, text=True,
                timeout=_COMMAND_TIMEOUT, check=False,
            )
        except subprocess.TimeoutExpired:
            return f"timed out after {_COMMAND_TIMEOUT}s: {command}"
        except FileNotFoundError:
            return f"executable not found: {argv[0]}"
        output = strip_ansi((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else ""))
        return clip(f"exit code {proc.returncode}\n{output}", 8000)

    return [list_dir, read_file, grep, edit_file, write_file, run_command]

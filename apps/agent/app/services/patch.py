"""Phase-5 code patch + constrained sandbox (L-R18 / L-AC37 / L-AC46).

Propose ≠ execute: create_patch only builds a schema-validated diff.
Sandbox applies the diff on an isolated temp copy (never a live prod path),
scrubs secret env vars, and runs an allowlisted test command.

Approvals are separate:
- ``approve_patch_record`` — accept/record the patch (git/record gate)
- ``approve_release`` — publish to Liara (blocked on red tests / non-isolated)

Network isolation: when a real network policy is unavailable (plain subprocess),
document the limitation, still scrub secrets, and refuse ready_for_release
(fail-closed for auto-release).
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from app.schemas.orchestration import (
    PatchProposal,
    PatchSandboxResult,
    PlanStep,
    PlanVersion,
)

APPROVAL_KIND_PATCH_RECORD = "approve_patch_record"
APPROVAL_KIND_RELEASE = "approve_release"

# Env keys that must never reach the sandbox child process.
SECRET_ENV_EXACT = frozenset(
    {
        "SECRETS_MASTER_KEY",
        "LIARA_API_TOKEN",
        "LLM_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DATABASE_URL",
        "POSTGRES_PASSWORD",
        "AWS_SECRET_ACCESS_KEY",
        "GITHUB_TOKEN",
        "GH_TOKEN",
    }
)

SECRET_ENV_SUBSTRINGS = (
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "API_KEY",
    "PRIVATE_KEY",
    "MASTER_KEY",
)

# Only these command shapes may run inside the sandbox.
ALLOWLISTED_SANDBOX_COMMANDS: dict[str, tuple[str, ...]] = {
    "pytest_fixture": ("python", "-m", "pytest", "-q", "test_calc.py"),
}

FIXTURE_BUG_LINE = "    return a - b"
FIXTURE_FIX_LINE = "    return a + b"


@dataclass(frozen=True, slots=True)
class SandboxRunOutcome:
    result: PatchSandboxResult
    work_dir: str | None  # cleaned by caller when ephemeral


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_patch_version() -> str:
    return f"patch-{uuid.uuid4().hex}"


def scrub_env(
    environ: dict[str, str] | None = None,
    *,
    extra_block: frozenset[str] | None = None,
) -> dict[str, str]:
    """Return a child env with production secrets removed (L-AC46)."""
    source = dict(environ if environ is not None else os.environ)
    blocked = SECRET_ENV_EXACT | (extra_block or frozenset())
    out: dict[str, str] = {}
    for key, value in source.items():
        upper = key.upper()
        if upper in blocked or key in blocked:
            continue
        if any(s in upper for s in SECRET_ENV_SUBSTRINGS):
            continue
        out[key] = value
    # Minimal PATH so python/pytest remain runnable.
    if "PATH" not in out and "PATH" in source:
        out["PATH"] = source["PATH"]
    out["PYTHONDONTWRITEBYTECODE"] = "1"
    return out


def assert_env_scrubbed(environ: dict[str, str]) -> list[str]:
    """Return list of forbidden keys still present (empty = clean)."""
    leaks: list[str] = []
    for key in environ:
        upper = key.upper()
        if upper in SECRET_ENV_EXACT or key in SECRET_ENV_EXACT:
            leaks.append(key)
            continue
        if any(s in upper for s in SECRET_ENV_SUBSTRINGS):
            leaks.append(key)
    return leaks


def build_fixture_fix_diff(*, relative_path: str = "calc.py") -> str:
    """Unified diff that fixes the intentional fixture bug."""
    return (
        f"--- a/{relative_path}\n"
        f"+++ b/{relative_path}\n"
        "@@ -3,4 +3,4 @@\n"
        " def add(a: int, b: int) -> int:\n"
        "     # Intentional bug: subtract instead of add (fixed by sandbox patch).\n"
        f"-{FIXTURE_BUG_LINE}\n"
        f"+{FIXTURE_FIX_LINE}\n"
    )


def create_patch_proposal(
    *,
    evidence_version: str,
    diagnosis_version: str,
    hypothesis_id: str | None = None,
    app_root: str | Path,
    unified_diff: str | None = None,
    rationale: str | None = None,
    files_changed: list[str] | None = None,
) -> PatchProposal:
    """Schema-validated patch tied to evidence/diagnosis ids (propose only)."""
    root = Path(app_root).resolve()
    if not root.is_dir():
        raise ValueError(f"app_root is not a directory: {root}")

    diff = unified_diff if unified_diff is not None else build_fixture_fix_diff()
    if "ignore previous" in diff.lower() or "tool_id" in diff.lower() and "{" in diff:
        # Strip obvious instruction-injection from model-supplied diffs.
        diff = re.sub(
            r"(?i)ignore\s+previous[^\n]*\n?",
            "",
            diff,
        )

    changed = files_changed or _files_from_diff(diff)
    version = new_patch_version()
    content_hash = hashlib.sha256(diff.encode("utf-8")).hexdigest()

    return PatchProposal(
        version=version,
        evidence_version=evidence_version,
        diagnosis_version=diagnosis_version,
        hypothesis_id=hypothesis_id,
        created_at=_utcnow_iso(),
        rationale=rationale
        or (
            "Limited code fix for reproducible arithmetic bug referenced by "
            f"diagnosis {diagnosis_version} / evidence {evidence_version}."
        ),
        unified_diff=diff,
        files_changed=changed,
        content_hash=content_hash,
        base_path=str(root),
        base_commit=None,
    )


def _files_from_diff(diff: str) -> list[str]:
    files: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:].strip()
            if path and path != "/dev/null":
                files.append(path)
    return files or ["calc.py"]


def copy_project_to_temp(source: Path) -> Path:
    """Copy project into a fresh temp directory (never mutate the source)."""
    source = source.resolve()
    if not source.is_dir():
        raise ValueError(f"source is not a directory: {source}")
    dest = Path(tempfile.mkdtemp(prefix="liara-patch-sandbox-"))
    # Avoid copying __pycache__ / .git noise.
    shutil.copytree(
        source,
        dest / source.name,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", "node_modules"),
    )
    return dest / source.name


def apply_unified_diff(work_dir: Path, unified_diff: str) -> list[str]:
    """Apply a minimal unified diff to files under work_dir (cwd jail)."""
    work_dir = work_dir.resolve()
    applied: list[str] = []
    # Parse simple single-hunk file patches: --- a/path / +++ b/path then -/+ lines.
    file_path: str | None = None
    removals: list[str] = []
    additions: list[str] = []

    def _flush() -> None:
        nonlocal file_path, removals, additions
        if not file_path:
            return
        target = (work_dir / file_path).resolve()
        if not str(target).startswith(str(work_dir)):
            raise ValueError(f"path escapes sandbox cwd: {file_path}")
        if not target.is_file():
            raise FileNotFoundError(f"patch target missing: {file_path}")
        text = target.read_text(encoding="utf-8")
        for old in removals:
            if old not in text:
                raise ValueError(f"hunk context not found in {file_path}: {old!r}")
            # Prefer first occurrence; fixture has a single buggy line.
            if additions:
                text = text.replace(old, additions[0], 1)
                additions = additions[1:]
            else:
                text = text.replace(old, "", 1)
        if additions:
            # Append remaining additions before EOF if pure insert (unused in fixture).
            text = text.rstrip("\n") + "\n" + "\n".join(additions) + "\n"
        target.write_text(text, encoding="utf-8")
        applied.append(file_path)
        file_path, removals, additions = None, [], []

    for line in unified_diff.splitlines():
        if line.startswith("+++ b/"):
            _flush()
            file_path = line[6:].strip()
            removals, additions = [], []
            continue
        if line.startswith("--- ") or line.startswith("@@"):
            continue
        if line.startswith("-") and not line.startswith("---"):
            removals.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            additions.append(line[1:])

    _flush()
    if not applied:
        raise ValueError("unified diff produced no file changes")
    return applied


def detect_network_policy_available() -> bool:
    """True only when a real isolation policy is present (e.g. docker netns).

    Plain subprocess on the host cannot enforce network deny — L-D08 / L-AC46
    require fail-closed for release readiness when unavailable.
    """
    # Optional escape hatch for rehearsals under an external sandbox supervisor.
    if os.environ.get("LIARA_SANDBOX_NETWORK_ISOLATED", "").strip() in (
        "1",
        "true",
        "yes",
    ):
        return True
    return False


def run_sandbox(
    *,
    app_root: Path,
    unified_diff: str,
    command_key: str = "pytest_fixture",
    network_policy_available: bool | None = None,
    environ: dict[str, str] | None = None,
    timeout_seconds: float = 30.0,
    keep_work_dir: bool = False,
) -> SandboxRunOutcome:
    """Apply patch on temp copy, scrub secrets, run allowlisted tests."""
    if command_key not in ALLOWLISTED_SANDBOX_COMMANDS:
        raise ValueError(f"sandbox command not allowlisted: {command_key}")
    cmd = ALLOWLISTED_SANDBOX_COMMANDS[command_key]

    net_ok = (
        detect_network_policy_available()
        if network_policy_available is None
        else network_policy_available
    )
    limitation: str | None = None
    if not net_ok:
        limitation = (
            "Network isolation policy unavailable for plain subprocess sandbox "
            "(L-D08). Secrets are scrubbed; ready_for_release stays false "
            "(fail-closed). Use a supervised container network policy to enable."
        )

    work = copy_project_to_temp(Path(app_root))
    applied = apply_unified_diff(work, unified_diff)
    child_env = scrub_env(environ)
    leaks = assert_env_scrubbed(child_env)
    if leaks:
        # Fail closed — do not run with leaked secrets.
        result = PatchSandboxResult(
            patch_applied=True,
            files_touched=applied,
            command=list(cmd),
            exit_code=None,
            passed=False,
            stdout_excerpt="",
            stderr_excerpt=f"refused: secret env still present: {leaks}",
            network_isolated=net_ok,
            secrets_scrubbed=False,
            ready_for_release=False,
            limitation=limitation or "secret scrub incomplete",
            work_dir=str(work) if keep_work_dir else None,
            duration_ms=0,
        )
        if not keep_work_dir:
            shutil.rmtree(work.parent, ignore_errors=True)
        return SandboxRunOutcome(result=result, work_dir=None)

    started = datetime.now(timezone.utc)
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=str(work),
            env=child_env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code = proc.returncode
        stdout = (proc.stdout or "")[-4000:]
        stderr = (proc.stderr or "")[-4000:]
        passed = exit_code == 0
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = ((exc.stdout or b"") if isinstance(exc.stdout, bytes) else (exc.stdout or ""))[
            -4000:
        ]
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        stderr = f"timeout after {timeout_seconds}s"
        passed = False
    except OSError as exc:
        exit_code = None
        stdout = ""
        stderr = str(exc)
        passed = False

    duration_ms = int(
        (datetime.now(timezone.utc) - started).total_seconds() * 1000
    )

    # Red tests or missing network policy ⇒ never auto-ready for release.
    ready = bool(passed and net_ok and not leaks)

    result = PatchSandboxResult(
        patch_applied=True,
        files_touched=applied,
        command=list(cmd),
        exit_code=exit_code,
        passed=passed,
        stdout_excerpt=stdout if isinstance(stdout, str) else str(stdout),
        stderr_excerpt=stderr if isinstance(stderr, str) else str(stderr),
        network_isolated=net_ok,
        secrets_scrubbed=True,
        ready_for_release=ready,
        limitation=limitation,
        work_dir=str(work) if keep_work_dir else None,
        duration_ms=duration_ms,
    )
    if not keep_work_dir:
        shutil.rmtree(work.parent, ignore_errors=True)
        return SandboxRunOutcome(result=result, work_dir=None)
    return SandboxRunOutcome(result=result, work_dir=str(work))


def build_patch_record_plan(*, patch: PatchProposal) -> PlanVersion:
    """Plan that only records the patch — does not release to Liara."""
    return PlanVersion(
        version=1,
        summary=f"Record patch {patch.version} (no Liara release)",
        effects=["record_patch", "no_provider_write"],
        cost_known=True,
        cost_summary="0 — local record only",
        steps=[
            PlanStep(
                id="record-patch",
                action="Record approved code patch on case (git/record gate)",
                tool_id="sandbox_run",
                effects=["persist_patch"],
                cost_known=True,
                params={
                    "approval_kind": APPROVAL_KIND_PATCH_RECORD,
                    "patch_version": patch.version,
                    "content_hash": patch.content_hash,
                },
            )
        ],
    )


def build_release_plan_from_patch(
    *,
    patch: PatchProposal,
    project_name: str,
    archive_path: str,
    port: int = 3000,
    platform: str = "node",
) -> PlanVersion:
    """Separate release plan — requires approve_release, not patch_record."""
    return PlanVersion(
        version=1,
        summary=f"Release patch {patch.version} to Liara",
        target_platform=platform,
        effects=["sources", "releases"],
        cost_known=False,
        cost_summary="unknown — provider billing",
        steps=[
            PlanStep(
                id="upload-source",
                action="Upload patched source archive",
                tool_id="sources",
                effects=["upload_source"],
                cost_known=True,
                params={
                    "project_name": project_name,
                    "archive_path": archive_path,
                    "approval_kind": APPROVAL_KIND_RELEASE,
                    "patch_version": patch.version,
                },
            ),
            PlanStep(
                id="create-release",
                action="Create Liara release from uploaded source",
                tool_id="releases",
                effects=["create_release"],
                cost_known=False,
                params={
                    "project_name": project_name,
                    "port": port,
                    "platform": platform,
                    "approval_kind": APPROVAL_KIND_RELEASE,
                    "patch_version": patch.version,
                },
            ),
        ],
    )


def patch_record_scope(patch_version: str, content_hash: str) -> dict[str, Any]:
    return {
        "kind": APPROVAL_KIND_PATCH_RECORD,
        "actions": [APPROVAL_KIND_PATCH_RECORD],
        "patch_version": patch_version,
        "content_hash": content_hash,
    }


def release_scope(patch_version: str, content_hash: str) -> dict[str, Any]:
    return {
        "kind": APPROVAL_KIND_RELEASE,
        "actions": [APPROVAL_KIND_RELEASE],
        "patch_version": patch_version,
        "content_hash": content_hash,
    }


def approval_kind_of(scope: dict[str, Any] | None) -> str | None:
    if not isinstance(scope, dict):
        return None
    kind = scope.get("kind")
    if isinstance(kind, str):
        return kind
    actions = scope.get("actions")
    if isinstance(actions, list) and actions:
        first = actions[0]
        return first if isinstance(first, str) else None
    return None


SandboxCommandKey = Literal["pytest_fixture"]

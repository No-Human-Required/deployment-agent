"""Liara read/write tools, HTTP verification and finish."""

from __future__ import annotations

import json
import re
import secrets
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pathspec
from langchain_core.tools import BaseTool, tool

from app.agent.context import AgentContext, clip, strip_ansi
from app.agent.tools.docs import html_to_text
from app.services.deploy import (
    _ARCHIVE_SKIP_BUILD_ARTIFACTS,
    _ARCHIVE_SKIP_DIR_NAMES,
    _ARCHIVE_SKIP_FILE_NAMES,
    _STUB_BODY_RE,
    pack_app_source_archive,
)
from app.services.dependencies import connection_url_from_database
from app.services.liara_client import LiaraClient, LiaraClientError, LiaraNotFoundError
from app.services.troubleshoot import sanitize_log_line

# Tools that pause the run for an explicit user approval (paid, destructive or DNS-visible).
GATED_TOOLS = frozenset(
    {"liara_create_app", "liara_create_database", "liara_create_disk", "liara_attach_domain"}
)

_SECRET_KEY_RE = re.compile(r"(?i)(pass|secret|token|private|credential|api[_-]?key|auth|salt|cookie)")
_URL_CREDS_RE = re.compile(r"(?i)([a-z][a-z0-9+.-]*://[^:/@\s]*:)([^@\s]+)(@)")
_LIARA_ERROR_PAGE_RE = re.compile(r"(?i)<title>\s*Liara \| Application Error")
_TITLE_RE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")
_FAILED_STATES = frozenset({"FAILED", "ERROR", "CANCELED", "CANCELLED"})
_READY_STATES = frozenset({"READY", "SUCCESS", "RUNNING", "DEPLOYED"})


def redact_env_value(key: str, value: Any) -> str:
    text = "" if value is None else str(value)
    if _URL_CREDS_RE.search(text):
        return _URL_CREDS_RE.sub(r"\1***\3", text)
    if _SECRET_KEY_RE.search(key):
        return f"***set ({len(text)} chars)***" if text else "(empty)"
    return text[:160]


# Same defaults as liara-cli createArchive; secrets and VCS are never uploaded regardless of ignore files.
_CLI_DEFAULT_IGNORES = (".git", ".idea", ".vscode", ".next", ".dockerignore", "*.*~", "liara.json", "node_modules", "bower_components", ".DS_Store")
_IGNORE_FILES = (".liaraignore", ".dockerignore", ".gitignore")


def _dir_ignore_spec(directory: Path) -> pathspec.GitIgnoreSpec | None:
    for name in _IGNORE_FILES:
        candidate = directory / name
        if candidate.is_file():
            lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
            return pathspec.GitIgnoreSpec.from_lines(lines)
    return None


def collect_archive_files(root: Path, *, include_build_output: bool = False) -> list[Path]:
    """Files Liara CLI would upload: per directory .liaraignore, else .dockerignore, else .gitignore."""
    root = root.resolve()
    defaults = pathspec.GitIgnoreSpec.from_lines(_CLI_DEFAULT_IGNORES)
    specs: list[tuple[Path, pathspec.GitIgnoreSpec]] = []
    out: list[Path] = []

    def ignored(path: Path, is_dir: bool) -> bool:
        name = path.name
        if (is_dir and name in _ARCHIVE_SKIP_DIR_NAMES) or name in _ARCHIVE_SKIP_FILE_NAMES:
            return True
        if not is_dir and name.startswith(".env") and name != ".env.example":
            return True
        rel = path.relative_to(root).as_posix() + ("/" if is_dir else "")
        if defaults.check_file(rel).include:
            return True
        if include_build_output and any(part in _ARCHIVE_SKIP_BUILD_ARTIFACTS for part in path.relative_to(root).parts):
            return False
        verdict: bool | None = None
        for base, spec in specs:
            try:
                sub = path.relative_to(base).as_posix() + ("/" if is_dir else "")
            except ValueError:
                continue
            result = spec.check_file(sub).include
            if result is not None:
                verdict = result
        return bool(verdict)

    def walk(directory: Path) -> None:
        spec = _dir_ignore_spec(directory)
        if spec is not None:
            specs.append((directory, spec))
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            entries = []
        for entry in entries:
            if entry.is_symlink():
                continue
            is_dir = entry.is_dir()
            if ignored(entry, is_dir):
                continue
            if is_dir:
                walk(entry)
            elif entry.is_file():
                out.append(entry)
        if spec is not None:
            specs.pop()

    walk(root)
    return out


def pack_plain_archive(root: Path, *, include_build_output: bool = False) -> Path:
    """tar.gz of the folder as liara-cli would pack it (no script rewriting)."""
    root = root.resolve()
    files = collect_archive_files(root, include_build_output=include_build_output)
    if not files:
        raise RuntimeError("every file is ignored — check .liaraignore / .gitignore")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    dest = Path(tempfile.gettempdir()) / f"liara-agent-{root.name}-{stamp}.tar.gz"
    with tarfile.open(dest, "w:gz") as archive:
        for file in files:
            archive.add(file, arcname=file.relative_to(root).as_posix(), recursive=False)
    return dest


def liara_json_release_fields(root: Path, platform: str) -> dict[str, Any]:
    """Release-body fields liara-cli derives from liara.json (the server never reads the file itself)."""
    path = root / "liara.json"
    if not path.is_file():
        return {}
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"liara.json is not valid JSON: {exc}") from exc
    if not isinstance(config, dict):
        return {}
    fields: dict[str, Any] = {}
    for key in ("port", "platform", "disks", "args", "cron"):
        if config.get(key) is not None:
            fields[key] = config[key]
    build = config.get("build")
    if isinstance(build, dict):
        fields["build"] = {k: build[k] for k in ("cache", "args", "dockerfile", "location") if k in build}
    platform_config = config.get(str(config.get("platform") or platform))
    if isinstance(platform_config, dict):
        fields["platformConfig"] = platform_config
    health = config.get("healthCheck")
    if isinstance(health, dict) and health.get("command"):
        health = dict(health)
        if isinstance(health["command"], str):
            health["command"] = health["command"].split(" ")
        fields["healthCheck"] = health
    return fields


def _release_summary(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r.get("_id"),
        "type": r.get("type"),
        "state": r.get("state"),
        "port": r.get("port"),
        "tag": r.get("tag"),
        "createdAt": r.get("createdAt"),
        "finishedAt": r.get("finishedAt"),
        "buildLocation": r.get("buildLocation"),
        "buildTimeoutMin": r.get("buildTimeout"),
        "disks": r.get("disks"),
    }


def build_liara_tools(ctx: AgentContext) -> list[BaseTool]:
    def client() -> LiaraClient:
        if ctx.liara is None:
            raise RuntimeError("Liara API token is not configured in Settings")
        return ctx.liara

    def project_of(name: str | None) -> str:
        return (name or ctx.project_name).strip()

    def write(tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = ctx.write_guard.execute_allowlisted(tool_id=tool_id, payload=payload)
        if result.get("mode") == "noop":
            raise RuntimeError("live Liara writes are disabled on this server (LIARA_ALLOW_LIVE_WRITES != 1)")
        safe = {k: v for k, v in payload.items() if k not in ("variables", "archive_path")}
        ctx.audit(f"agent.write.{tool_id}", {"payload": safe, "result_keys": sorted(result.keys())})
        return result

    def current_envs(project: str) -> list[dict[str, str]]:
        return [
            {"key": str(e.get("key")), "value": str(e.get("value") or "")}
            for e in client().project_envs(project)
            if e.get("key")
        ]

    # --- reads -------------------------------------------------------------------

    @tool
    def liara_list_apps() -> str:
        """List all PaaS apps on the Liara account (name, platform, status)."""
        rows = client().list_projects()
        return "\n".join(
            f"{p.get('project_id') or p.get('name')}  type={p.get('type')} status={p.get('status')} plan={p.get('planID')}"
            for p in rows
        ) or "(no apps)"

    @tool
    def liara_get_project(project_name: str | None = None) -> str:
        """Show a Liara app: status, plan, network, disks and env vars (secret values redacted)."""
        name = project_of(project_name)
        try:
            p = client().get_project(name)
        except LiaraNotFoundError:
            return f"app '{name}' does not exist on this account"
        envs = "\n".join(
            f"  {e.get('key')}={redact_env_value(str(e.get('key')), e.get('value'))}" for e in p.get("envs") or []
        )
        net = p.get("network") if isinstance(p.get("network"), dict) else {}
        return (
            f"app={name} type={p.get('type')} status={p.get('status')} plan={p.get('planID')} "
            f"deployed={p.get('isDeployed')} network={net.get('name')} zeroDowntime={p.get('zeroDowntime')} "
            f"readOnlyRootFilesystem={p.get('readOnlyRootFilesystem')}\nurl=https://{name}.liara.run\nenvs:\n{envs or '  (none)'}"
        )

    @tool
    def liara_list_releases(project_name: str | None = None, limit: int = 8) -> str:
        """List recent releases (DEPLOY / ENV_UPDATE / RESTART) with state BUILDING|READY|FAILED and port."""
        data = client().list_releases(project_of(project_name))
        items = data.get("releases") if isinstance(data.get("releases"), list) else []
        lines = [f"currentRelease={data.get('currentRelease')}"]
        lines += [str(_release_summary(r)) for r in items[: max(1, min(limit, 20))] if isinstance(r, dict)]
        return "\n".join(lines)

    @tool
    def liara_build_logs(release_id: str, tail: int = 80) -> str:
        """Build output of a release (use when a DEPLOY release is FAILED or stuck BUILDING)."""
        data = client().get_build_logs(release_id)
        lines = [strip_ansi(row["line"]).rstrip("\n") for row in data["lines"]]
        lines = [ln for ln in lines if ln.strip()]
        body = "\n".join(sanitize_log_line(ln)[0] for ln in lines[-max(10, min(tail, 300)) :])
        return clip(f"release {release_id} state={data['state']}\n{body}")

    @tool
    def liara_runtime_logs(
        project_name: str | None = None, lines: int = 80, release_id: str | None = None, since_minutes: int = 30
    ) -> str:
        """Runtime stdout/stderr of the running app (crash stacks, 'listening on', DB errors). Oldest first."""
        since = int(time.time()) - max(1, since_minutes) * 60
        rows = client().get_runtime_logs(project_of(project_name), since=since)
        if release_id:
            rows = [r for r in rows if r.get("release_id") == release_id]
        picked = rows[-max(10, min(lines, 400)) :]
        out = []
        for r in picked:
            msg, _ = sanitize_log_line(strip_ansi(str(r.get("message") or "")))
            rel = str(r.get("release_id") or "")[-6:]
            out.append(f"[{r.get('stream')}|{rel}] {msg}")
        return clip("\n".join(out) or "(no log lines in this window — the app may not have started yet)")

    @tool
    def liara_list_databases() -> str:
        """List managed databases (id, hostname, type, status, private network)."""
        rows = client().list_databases()
        return "\n".join(
            f"id={d.get('_id')} hostname={d.get('hostname')} type={d.get('type')} status={d.get('status')} "
            f"version={d.get('version')} network={(d.get('network') or {}).get('name')} plan={d.get('planID')}"
            for d in rows
        ) or "(no databases)"

    # --- writes (auto-approved within the run) -------------------------------------

    @tool
    def liara_deploy(
        app_dir: str = ".",
        port: int | None = None,
        platform: str | None = None,
        project_name: str | None = None,
        pack_mode: str = "plain",
        include_build_output: bool = False,
        build_location: str | None = None,
        build_cache: bool | None = None,
    ) -> str:
        """Package a project folder, upload it and create a release on Liara, then wait for the build.

        Behaves like `liara deploy` run inside app_dir: honours .liaraignore (else .dockerignore, else
        .gitignore) per directory, never uploads liara.json/.env, and sends liara.json settings
        (port, platform, disks, build.location/cache/args, <platform>.version, healthCheck) with the release.
        app_dir: folder inside the project to deploy (monorepo: "." for root or "apps/api").
        port: the port the app listens on inside the container (default: liara.json port, else 3000).
        platform: node | next | static | docker | react | vue | angular | python | django | flask | laravel | php | go | dotnet.
        pack_mode: "plain" uploads the folder (Liara runs npm ci/install, npm run build, npm start).
                   "prebuilt" builds NestJS locally and ships dist/ (use only if the Liara build itself keeps failing).
        include_build_output: upload dist/ and build/ even if ignore files exclude them.
        build_location: "iran" (fast push, restricted downloads) or "germany" (unrestricted npm/pip downloads).
        build_cache: false to rebuild without Liara's build cache.
        Returns the final release state; on FAILED includes the build-log tail and build duration.
        """
        name = project_of(project_name)
        if ctx.redeploys >= ctx.budget.max_redeploys:
            return f"redeploy budget exhausted ({ctx.budget.max_redeploys}); finish with what you know"
        try:
            client().get_project(name)
        except LiaraNotFoundError:
            return f"app '{name}' does not exist; create it first with liara_create_app (needs user approval)"
        root = ctx.resolve_path(app_dir)
        if not root.is_dir():
            return f"not a directory: {app_dir}"
        cfg = liara_json_release_fields(root, platform or "node")
        platform = platform or str(cfg.get("platform") or "node")
        port = int(port or cfg.get("port") or 3000)
        build = dict(cfg.get("build") or {})
        if build_location:
            build["location"] = build_location
        if build_cache is not None:
            build["cache"] = bool(build_cache)
        archive = (
            pack_app_source_archive(root)
            if pack_mode == "prebuilt"
            else pack_plain_archive(root, include_build_output=include_build_output)
        )
        size_mb = archive.stat().st_size / 1_000_000
        if size_mb > 200:
            return f"archive is {size_mb:.0f} MB — too large; add a .liaraignore or check app_dir"

        disks: list[dict[str, Any]] | None = cfg.get("disks") if isinstance(cfg.get("disks"), list) else None
        if disks is None:
            try:
                prior = client().list_releases(name).get("releases") or []
                last_deploy = next((r for r in prior if isinstance(r, dict) and r.get("type") == "DEPLOY"), None)
                if last_deploy and last_deploy.get("disks"):
                    disks = [{"name": d.get("name"), "mountTo": d.get("mountTo")} for d in last_deploy["disks"]]
            except LiaraClientError:
                disks = None

        ctx.redeploys += 1
        ctx.emit({"type": "deploy", "phase": "upload", "app": name, "app_dir": ctx.rel(root), "port": port, "size_mb": round(size_mb, 2)})
        source = write("sources", {"project_name": name, "archive_path": str(archive)})
        payload: dict[str, Any] = {"project_name": name, "sourceID": source["sourceID"], "port": port, "platform": platform}
        if disks:
            payload["disks"] = disks
        if build:
            payload["build"] = build
        for key in ("platformConfig", "healthCheck", "args", "cron"):
            if cfg.get(key):
                payload[key] = cfg[key]
        started = time.monotonic()
        release = write("releases", payload)
        release_id = str(release.get("releaseID"))
        ctx.emit({"type": "deploy", "phase": "building", "app": name, "release_id": release_id})

        deadline = time.monotonic() + min(10 * 60, max(60, ctx.seconds_left() - 60))
        state = "BUILDING"
        last_emit = 0.0
        while time.monotonic() < deadline:
            items = client().list_releases(name).get("releases") or []
            match = next((r for r in items if isinstance(r, dict) and r.get("_id") == release_id), None)
            state = str((match or {}).get("state") or "UNKNOWN").upper()
            if state in _FAILED_STATES or state in _READY_STATES:
                break
            if time.monotonic() - last_emit > 30:
                ctx.emit({"type": "deploy", "phase": "building", "app": name, "release_id": release_id, "state": state})
                last_emit = time.monotonic()
            ctx.sleep(10)
        ctx.emit({"type": "deploy", "phase": "done", "app": name, "release_id": release_id, "state": state})
        if state in _FAILED_STATES:
            elapsed = round(time.monotonic() - started)
            timeout_min = (match or {}).get("buildTimeout")
            logs = liara_build_logs.invoke({"release_id": release_id, "tail": 60})
            return (
                f"release {release_id} {state} (build failed) after ~{elapsed}s "
                f"(buildTimeout={timeout_min} min, sent: platform={platform} build={build or {}} "
                f"platformConfig={cfg.get('platformConfig') or {}}). Liara often cuts the log at the failing step "
                f"without the error text; reproduce that step locally (run_command) to see the real error.\n"
                f"Build log tail:\n{logs}"
            )
        if state in _READY_STATES:
            return (
                f"release {release_id} READY on port {port} (disks={disks}). The container is starting: "
                f"http_check with wait_seconds=60, and read liara_runtime_logs if it is not 2xx."
            )
        return f"release {release_id} still {state} after waiting; check liara_list_releases / liara_build_logs"

    @tool
    def liara_set_envs(
        variables: dict[str, str] | None = None,
        generate_secrets: list[str] | None = None,
        remove: list[str] | None = None,
        project_name: str | None = None,
    ) -> str:
        """Merge env vars into the app (other keys are kept) and restart it via an ENV_UPDATE release.

        variables: {"KEY": "value"} to add or change (never invent real third-party credentials).
        generate_secrets: keys to fill with a fresh random secret (JWT/session secrets).
        remove: keys to delete.
        """
        name = project_of(project_name)
        merged = {e["key"]: e["value"] for e in current_envs(name)}
        changed: list[str] = []
        for key, value in (variables or {}).items():
            merged[str(key)] = str(value)
            changed.append(str(key))
        for key in generate_secrets or []:
            merged[str(key)] = secrets.token_urlsafe(48)
            changed.append(f"{key}(generated)")
        for key in remove or []:
            if merged.pop(str(key), None) is not None:
                changed.append(f"-{key}")
        if not changed:
            return "nothing to change"
        write("update_envs", {"project": name, "variables": [{"key": k, "value": v} for k, v in merged.items()]})
        ctx.emit({"type": "envs", "app": name, "changed": changed})
        return f"envs updated on {name}: {', '.join(changed)}. Liara restarts the app (ENV_UPDATE); wait ~30s then http_check."

    @tool
    def liara_connect_database(
        database_id: str, env_key: str = "DATABASE_URL", db_name: str | None = None, project_name: str | None = None
    ) -> str:
        """Build the private-network connection URL for a managed database and set it as an env var.

        The password is filled in server-side and never shown to you. db_name defaults to the
        engine default (Postgres: "postgres"). Triggers an app restart.
        """
        details = client().get_database(database_id)
        database = details.get("database") if isinstance(details.get("database"), dict) else details
        db_type = str(database.get("type") or "postgres")
        url = connection_url_from_database(details, db_type=db_type, db_name=db_name)
        if not url:
            return "could not build a connection URL (database not ready or missing credentials)"
        name = project_of(project_name)
        merged = {e["key"]: e["value"] for e in current_envs(name)}
        merged[env_key] = url
        write("update_envs", {"project": name, "variables": [{"key": k, "value": v} for k, v in merged.items()]})
        ctx.emit({"type": "envs", "app": name, "changed": [env_key]})
        return f"{env_key} set on {name} to {redact_env_value(env_key, url)}; the app restarts."

    @tool
    def liara_restart(project_name: str | None = None) -> str:
        """Restart the app (no rebuild)."""
        name = project_of(project_name)
        write("restart", {"project_name": name})
        return f"restart requested for {name}; wait ~30s then http_check"

    # --- gated writes (run pauses for user approval first) -----------------------------

    @tool
    def liara_create_app(name: str, platform: str = "node", plan_id: str = "small-g2") -> str:
        """Create a new PaaS app on Liara (paid; needs user approval). Uses the account's existing private network."""
        result = write("create_project", {"name": name, "platform": platform, "planID": plan_id, "readOnlyRootFilesystem": False})
        return f"app created: {result.get('project_name', name)} → https://{name}.liara.run"

    @tool
    def liara_create_database(hostname: str, db_type: str = "postgres", version: str = "16", plan_id: str = "small-g2") -> str:
        """Create a managed database on the app's private network (paid; needs user approval). Takes 1-3 min to be ready.

        version must be one Liara offers (e.g. "16.14" for postgres); if rejected, read the DBaaS docs for valid versions.
        """
        network = None
        try:
            net = client().get_project(ctx.project_name).get("network")
            network = net.get("_id") if isinstance(net, dict) else None
        except LiaraClientError:
            network = None
        result = write(
            "create_database",
            {"hostname": hostname, "type": db_type, "version": version, "planID": plan_id, "network": network or client().ensure_network()},
        )
        return f"database creation accepted: id={result.get('databaseID')} hostname={hostname}. Poll liara_list_databases until RUNNING, then liara_connect_database."

    @tool
    def liara_create_disk(name: str, size_gb: int = 1, project_name: str | None = None) -> str:
        """Create a persistent disk for an app (paid; needs user approval). Mount it on the next liara_deploy via release disks."""
        app = project_of(project_name)
        write("create_disk", {"project_name": app, "name": name, "size": str(size_gb)})
        return f"disk '{name}' ({size_gb} GB) created on {app}"

    @tool
    def liara_attach_domain(domain: str, project_name: str | None = None) -> str:
        """Attach a custom domain to the app (needs user approval). DNS must then point to Liara."""
        app = project_of(project_name)
        result = write("create_domain", {"name": domain, "project": app, "type": "PROJECT"})
        return f"domain {domain} added to {app}: {result}"

    # --- verification --------------------------------------------------------------------

    def _get(url: str) -> tuple[int, str, str]:
        if ctx.http_get is not None:
            return ctx.http_get(url)
        import httpx

        with httpx.Client(timeout=15.0, follow_redirects=True) as http:
            resp = http.get(url, headers={"User-Agent": "liara-devops-agent/1.0"})
            return resp.status_code, resp.headers.get("content-type", ""), resp.text[:200_000]

    @tool
    def http_check(url: str | None = None, path: str = "/", wait_seconds: int = 0) -> str:
        """GET the app URL (default https://<app>.liara.run) and judge whether it serves the real app.

        wait_seconds: keep retrying every 10 s up to this long while it is not healthy (max 300).
        """
        target = (url or ctx.app_url).rstrip("/") + (path if path.startswith("/") else f"/{path}")
        deadline = time.monotonic() + max(0, min(wait_seconds, 300))
        attempts = 0
        while True:
            attempts += 1
            try:
                status, ctype, body = _get(target)
                error = None
            except Exception as exc:  # noqa: BLE001 — network errors are evidence, not crashes
                status, ctype, body, error = 0, "", "", f"{type(exc).__name__}: {exc}"[:200]
            title_match = _TITLE_RE.search(body or "")
            title = html_to_text(title_match.group(1)).strip()[:120] if title_match else ""
            text = html_to_text(body) if "html" in ctype else (body or "")
            liara_error = bool(_LIARA_ERROR_PAGE_RE.search(body or "")) or status in (502, 503, 504)
            stub = bool(_STUB_BODY_RE.search(text.strip()[:200]))
            ok = 200 <= status < 400 and not liara_error and not stub
            if ok or time.monotonic() >= deadline:
                break
            ctx.sleep(10)
        verdict = (
            "OK — serves a real response"
            if ok
            else "LIARA 502/ERROR PAGE — app not reachable (crash, wrong port, or not bound to 0.0.0.0); read liara_runtime_logs"
            if liara_error
            else "STUB BODY — a placeholder is deployed, not the real app"
            if stub
            else f"NOT OK ({error or status})"
        )
        host = urlparse(target).hostname
        if host == urlparse(ctx.app_url).hostname:
            ctx.last_http = {"url": target, "status": status, "ok": ok, "title": title}
        ctx.emit({"type": "http_check", "url": target, "status": status, "ok": ok, "title": title})
        preview = re.sub(r"\s+", " ", text)[:600]
        return f"{verdict}\nurl={target} status={status} attempts={attempts} content-type={ctype} title={title!r}\nbody: {preview}"

    @tool
    def wait(seconds: int = 30) -> str:
        """Pause (max 120 s) e.g. while a release builds or the app restarts."""
        s = max(1, min(seconds, 120))
        ctx.sleep(s)
        return f"waited {s}s"

    @tool
    def finish(success: bool, summary: str) -> str:
        """End the run. success=true is accepted only after http_check on the app URL returned a real page.

        summary: Persian, for the end user — what was wrong, what you changed, the URL, and anything they must do.
        """
        return "finish requested"

    return [
        liara_list_apps,
        liara_get_project,
        liara_list_releases,
        liara_build_logs,
        liara_runtime_logs,
        liara_list_databases,
        liara_deploy,
        liara_set_envs,
        liara_connect_database,
        liara_restart,
        liara_create_app,
        liara_create_database,
        liara_create_disk,
        liara_attach_domain,
        http_check,
        wait,
        finish,
    ]

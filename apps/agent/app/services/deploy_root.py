"""Resolve which directory to package for Liara PaaS when the workspace is a monorepo."""

from __future__ import annotations

import json
from pathlib import Path


_PREFERRED_APP_DIRS = (
    "apps/api",
    "apps/server",
    "apps/backend",
    "apps/web",
    "packages/api",
    "api",
    "server",
    "backend",
)


def _has_start_script(pkg: dict) -> bool:
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    for key in ("start", "start:prod", "start:production"):
        val = scripts.get(key)
        if isinstance(val, str) and val.strip():
            return True
    return False


def _read_package(path: Path) -> dict | None:
    pkg_path = path / "package.json"
    if not pkg_path.is_file():
        return None
    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def resolve_deploy_app_root(app_path: str | Path) -> Path:
    """Prefer a runnable workspace package over a monorepo root without ``start``."""
    root = Path(app_path).expanduser().resolve()
    if not root.is_dir():
        return root

    root_pkg = _read_package(root)
    if root_pkg and _has_start_script(root_pkg):
        return root

    for rel in _PREFERRED_APP_DIRS:
        candidate = root / rel
        pkg = _read_package(candidate)
        if pkg and _has_start_script(pkg):
            return candidate

    # First nested package.json with a start script (depth-limited).
    if root_pkg and root_pkg.get("workspaces"):
        for pkg_file in sorted(root.glob("*/package.json")) + sorted(
            root.glob("apps/*/package.json")
        ):
            candidate = pkg_file.parent
            pkg = _read_package(candidate)
            if pkg and _has_start_script(pkg):
                return candidate

    return root


def default_liara_app_url(project_name: str) -> str:
    """Default public URL for a Liara PaaS app (iran region)."""
    name = (project_name or "").strip().strip("/")
    return f"https://{name}.liara.run"

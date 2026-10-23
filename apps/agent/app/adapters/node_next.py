"""Node.js / Next.js readiness adapter — file-backed findings only.

Inspects package.json and common Next config files. Does not mutate the app
or call Liara. Findings always include evidence paths under the inspected root.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ReadinessFinding:
    code: str
    message: str
    evidence_paths: tuple[str, ...]
    severity: str = "error"  # error | warn | info


@dataclass(frozen=True, slots=True)
class NodeNextReadiness:
    ready: bool
    platform: str  # nodejs | next | unknown
    findings: tuple[ReadinessFinding, ...] = ()
    package_name: str | None = None
    detected_port: int | None = None
    start_script: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "platform": self.platform,
            "package_name": self.package_name,
            "detected_port": self.detected_port,
            "start_script": self.start_script,
            "notes": self.notes,
            "findings": [
                {
                    "code": f.code,
                    "message": f.message,
                    "evidence_paths": list(f.evidence_paths),
                    "severity": f.severity,
                }
                for f in self.findings
            ],
        }


def assess_node_next(app_root: str | Path) -> NodeNextReadiness:
    """Assess a local Node/Next app directory for first-publish readiness."""
    root = Path(app_root).resolve()
    findings: list[ReadinessFinding] = []

    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        findings.append(
            ReadinessFinding(
                code="missing_package_json",
                message="package.json not found",
                evidence_paths=(str(pkg_path),),
            )
        )
        return NodeNextReadiness(
            ready=False,
            platform="unknown",
            findings=tuple(findings),
            notes="not a Node app root",
        )

    try:
        package = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(
            ReadinessFinding(
                code="invalid_package_json",
                message=f"package.json unreadable: {exc}",
                evidence_paths=(str(pkg_path),),
            )
        )
        return NodeNextReadiness(
            ready=False,
            platform="unknown",
            findings=tuple(findings),
        )

    if not isinstance(package, dict):
        findings.append(
            ReadinessFinding(
                code="invalid_package_json",
                message="package.json root must be an object",
                evidence_paths=(str(pkg_path),),
            )
        )
        return NodeNextReadiness(
            ready=False,
            platform="unknown",
            findings=tuple(findings),
        )

    deps = {
        **(package.get("dependencies") or {}),
        **(package.get("devDependencies") or {}),
    }
    scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
    is_next = "next" in deps or _has_next_config(root)
    platform = "next" if is_next else "nodejs"

    start_script = None
    for key in ("start", "start:prod", "start:production"):
        if key in scripts and isinstance(scripts[key], str) and scripts[key].strip():
            start_script = scripts[key].strip()
            break

    if not start_script:
        findings.append(
            ReadinessFinding(
                code="missing_start_script",
                message="package.json scripts.start (or start:prod) is missing",
                evidence_paths=(str(pkg_path),),
            )
        )

    port = _detect_port(package, scripts, root)
    if port is None:
        evidence = [str(pkg_path)]
        next_cfg = _next_config_path(root)
        if next_cfg is not None:
            evidence.append(str(next_cfg))
        findings.append(
            ReadinessFinding(
                code="missing_port",
                message=(
                    "No listen port found (PORT env, scripts, liara.json, "
                    "or next config heuristic)"
                ),
                evidence_paths=tuple(evidence),
            )
        )

    if is_next and not (root / "next.config.js").exists() and not (
        root / "next.config.mjs"
    ).exists() and not (root / "next.config.ts").exists():
        # Soft signal only — Next can run without a config file.
        findings.append(
            ReadinessFinding(
                code="next_without_config",
                message="Next dependency present but no next.config.* found",
                evidence_paths=(str(pkg_path),),
                severity="warn",
            )
        )

    errors = [f for f in findings if f.severity == "error"]
    return NodeNextReadiness(
        ready=len(errors) == 0,
        platform=platform,
        findings=tuple(findings),
        package_name=str(package.get("name")) if package.get("name") else None,
        detected_port=port,
        start_script=start_script,
        notes=f"inspected {root}",
    )


def _has_next_config(root: Path) -> bool:
    return _next_config_path(root) is not None


def _next_config_path(root: Path) -> Path | None:
    for name in ("next.config.js", "next.config.mjs", "next.config.ts", "next.config.cjs"):
        path = root / name
        if path.is_file():
            return path
    return None


def _detect_port(
    package: dict[str, Any], scripts: dict[str, Any], root: Path
) -> int | None:
    # Explicit liara.json / package "port" / engines-style hints
    for key in ("port", "liaraPort"):
        raw = package.get(key)
        if isinstance(raw, int) and 1 <= raw <= 65535:
            return raw
        if isinstance(raw, str) and raw.isdigit():
            value = int(raw)
            if 1 <= value <= 65535:
                return value

    liara_json = root / "liara.json"
    if liara_json.is_file():
        try:
            data = json.loads(liara_json.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for key in ("port", "appPort"):
                    raw = data.get(key)
                    if isinstance(raw, int) and 1 <= raw <= 65535:
                        return raw
        except (OSError, json.JSONDecodeError):
            pass

    # Script heuristics: "-p 3000", "--port=3000", "PORT=3000"
    port_re = re.compile(
        r"(?:(?:^|[\s=])PORT=|--port=|-p\s+)(\d{2,5})\b", re.IGNORECASE
    )
    for script in scripts.values():
        if not isinstance(script, str):
            continue
        match = port_re.search(script)
        if match:
            value = int(match.group(1))
            if 1 <= value <= 65535:
                return value

    return None

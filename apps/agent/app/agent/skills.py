"""Agent skills — Markdown playbooks with frontmatter, loaded on demand."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent / "skills"

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    description: str
    body: str


def _parse(path: Path) -> Skill | None:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    name = meta.get("name") or path.parent.name
    return Skill(name=name, description=meta.get("description", ""), body=match.group(2).strip())


@lru_cache(maxsize=1)
def load_skills() -> dict[str, Skill]:
    skills: dict[str, Skill] = {}
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        skill = _parse(path)
        if skill is not None:
            skills[skill.name] = skill
    return skills


def skills_index() -> str:
    return "\n".join(f"- `{s.name}`: {s.description}" for s in load_skills().values())

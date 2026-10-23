"""Liara docs, general web fetch, and skills tools."""

from __future__ import annotations

import html
import ipaddress
import re
import socket
import time
from urllib.parse import urljoin, urlparse

import httpx
from langchain_core.tools import BaseTool, tool

from app.agent.context import AgentContext, clip
from app.agent.skills import load_skills, skills_index

LIARA_DOCS_HOST = "docs.liara.ir"
_MAX_BYTES = 2_000_000
_SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>")
_TAG_RE = re.compile(r"(?s)<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_BLANKS_RE = re.compile(r"\n\s*\n\s*\n+")


def html_to_text(raw: str) -> str:
    text = _SCRIPT_STYLE_RE.sub(" ", raw)
    text = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr|pre)>", "\n", text)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    return _BLANKS_RE.sub("\n\n", text).strip()


def _assert_public_host(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"cannot resolve host {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise PermissionError(f"refusing to fetch non-public address for {host}")


def safe_get(url: str, *, timeout: float = 20.0, attempts: int = 3) -> tuple[int, str, str]:
    """GET a public https URL (manual redirects, each hop re-checked). Returns (status, content_type, text)."""
    for attempt in range(attempts):
        try:
            return _safe_get_once(url, timeout=timeout)
        except httpx.TransportError:
            if attempt == attempts - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise AssertionError("unreachable")


def _safe_get_once(url: str, *, timeout: float) -> tuple[int, str, str]:
    current = url
    for _ in range(4):
        parsed = urlparse(current)
        if parsed.scheme != "https" or not parsed.hostname:
            raise PermissionError("only https:// URLs are allowed")
        _assert_public_host(parsed.hostname)
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            with client.stream("GET", current, headers={"User-Agent": "liara-devops-agent/1.0"}) as resp:
                if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                    current = urljoin(current, resp.headers["location"])
                    continue
                chunks: list[bytes] = []
                size = 0
                for chunk in resp.iter_bytes():
                    size += len(chunk)
                    if size > _MAX_BYTES:
                        break
                    chunks.append(chunk)
                body = b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
                return resp.status_code, resp.headers.get("content-type", ""), body
    raise ValueError("too many redirects")


def _docs_url(path_or_url: str) -> str:
    raw = path_or_url.strip()
    if raw.startswith("http"):
        parsed = urlparse(raw)
        if parsed.hostname != LIARA_DOCS_HOST:
            raise PermissionError("liara_docs_fetch only reads docs.liara.ir; use web_fetch for other sites")
        path = parsed.path
    else:
        path = raw if raw.startswith("/") else f"/{raw}"
    if path.endswith(".txt"):
        return f"https://{LIARA_DOCS_HOST}{path}"
    path = path.rstrip("/")
    if not path.startswith("/llms/"):
        path = f"/llms{path}"
    if not path.endswith(".md"):
        path = f"{path}.md"
    return f"https://{LIARA_DOCS_HOST}{path}"


def _grep_lines(text: str, query: str, context: int = 1) -> str:
    words = [w for w in query.lower().split() if w]
    lines = text.splitlines()
    keep: set[int] = set()
    for i, line in enumerate(lines):
        low = line.lower()
        if all(w in low for w in words):
            keep.update(range(max(0, i - context), min(len(lines), i + context + 1)))
    if not keep:
        return f"(no lines matching '{query}')"
    return "\n".join(lines[i] for i in sorted(keep))


def build_docs_tools(ctx: AgentContext) -> list[BaseTool]:
    @tool
    def list_skills() -> str:
        """List the DevOps/Liara playbooks (skills) you can load with load_skill."""
        return skills_index()

    @tool
    def load_skill(name: str) -> str:
        """Load the full text of a skill playbook by name (see list_skills)."""
        skill = load_skills().get(name.strip())
        if skill is None:
            return f"unknown skill '{name}'. Available:\n{skills_index()}"
        ctx.emit({"type": "skill", "name": skill.name})
        return skill.body

    @tool
    def liara_docs_index() -> str:
        """Read the Liara documentation index (docs.liara.ir/llms.txt) with section links."""
        status, _, body = safe_get(f"https://{LIARA_DOCS_HOST}/llms.txt")
        return clip(f"HTTP {status}\n{body}")

    @tool
    def liara_docs_fetch(path_or_url: str, query: str | None = None) -> str:
        """Read a Liara docs page as markdown.

        path_or_url: e.g. "/paas/nodejs/related-apps/nestjs", "paas/details/envs",
        a full https://docs.liara.ir/... URL, or "/all-links-llms.txt" (every page).
        query: optional words; when given, only matching lines (with context) are returned —
        use this with /all-links-llms.txt to find the right page.
        """
        url = _docs_url(path_or_url)
        ctx.emit({"type": "docs", "url": url})
        status, _, body = safe_get(url)
        if status >= 400:
            return f"HTTP {status} for {url}. Use liara_docs_fetch('/all-links-llms.txt', query=...) to find the right page."
        if query:
            body = _grep_lines(body, query)
        return clip(f"{url}\n\n{body}")

    @tool
    def web_fetch(url: str, query: str | None = None) -> str:
        """Fetch any public https web page (framework docs, npm package pages, GitHub issues) as text.

        query: optional words to keep only matching lines.
        """
        ctx.emit({"type": "docs", "url": url})
        status, content_type, body = safe_get(url)
        text = html_to_text(body) if "html" in content_type else body
        if query:
            text = _grep_lines(text, query, context=2)
        return clip(f"HTTP {status} {url}\n\n{text}", 10_000)

    return [list_skills, load_skill, liara_docs_index, liara_docs_fetch, web_fetch]

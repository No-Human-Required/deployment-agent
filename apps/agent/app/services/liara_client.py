"""Liara HTTP client — reads + allowlisted writes; sanitize before logging.

Auth: ``Authorization: Bearer <TOKEN>`` (docs.liara.ir / developers.liara.ir).
Team scope: optional ``teamID`` query parameter when set (Liara team API docs).
Base URL default: ``https://api.liara.ir``.
DNS base default: ``https://dns-service.liara.ir`` (developers.liara.ir DNS API).

Verified paths (developers.liara.ir OpenAPI):
- ``GET /v1/me``, ``GET /v1/projects``, ``GET /v1/projects/{name}``
- ``GET /v1/projects/{name}/releases``
- ``GET /v1/projects/{name}/logs``, ``/events``, ``/metrics/cpu``, ``/metrics/memory``
- ``POST /v1/projects`` (create app)
- ``POST /v2/projects/{name}/sources`` (multipart .gz → sourceID)
- ``POST /v2/projects/{name}/releases`` (sourceID + port + type → releaseID)
- ``POST /v1/projects/update-envs`` (merge/replace semantics undocumented — L-D03)
- ``POST /v1/projects/{name}/actions/restart``, ``POST /v1/projects/{name}/resize``
- ``POST /v1/domains``, ``GET /v1/domains``, ``GET /v1/domains/{id}/check``
- ``POST /v1/domains/set-project``, ``POST /v1/domains/provision-ssl-certs``
- DNS: ``GET /api/v1/zones``, ``POST /api/v1/zones/{zone}/dns-records``
- DBaaS: ``GET/POST /v1/databases``, ``GET /v1/databases/{id}`` (L-D05 — create gated)
- Disks: ``GET /v1/projects/{id}/disks``, ``POST /v1/projects/{name}/disks``
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.config import DEFAULT_DNS_API_BASE_URL, DEFAULT_LIARA_API_BASE_URL

logger = logging.getLogger(__name__)

# Never log raw tokens or long opaque strings that look like credentials.
_SENSITIVE_RE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._\-]+|eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+|"
    r"api[_-]?key[\"']?\s*[:=]\s*[\"']?[^\s\"']+)"
)


def sanitize_for_log(text: str | None, *, limit: int = 200) -> str:
    if not text:
        return ""
    cleaned = _SENSITIVE_RE.sub("[redacted]", text)
    if len(cleaned) > limit:
        return cleaned[:limit] + "…"
    return cleaned


class LiaraClientError(Exception):
    """Base classified Liara client failure."""

    code: str = "liara_error"

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "status_code": self.status_code,
        }


class LiaraUnauthorizedError(LiaraClientError):
    code = "unauthorized"


class LiaraForbiddenError(LiaraClientError):
    code = "forbidden"


class LiaraNotFoundError(LiaraClientError):
    code = "not_found"


class LiaraRateLimitError(LiaraClientError):
    code = "rate_limited"


class LiaraTimeoutError(LiaraClientError):
    code = "timeout"


class LiaraHttpError(LiaraClientError):
    code = "http_error"


@dataclass(frozen=True, slots=True)
class ProveReadResult:
    me: dict[str, Any]
    projects: list[dict[str, Any]]
    project_count: int


class LiaraClient:
    def __init__(
        self,
        token: str,
        *,
        base_url: str = DEFAULT_LIARA_API_BASE_URL,
        dns_base_url: str = DEFAULT_DNS_API_BASE_URL,
        team_id: str | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not token:
            raise ValueError("Liara API token is required")
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._dns_base_url = dns_base_url.rstrip("/")
        self._team_id = team_id.strip() if team_id else None
        self._timeout = timeout
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

    def _params(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        params: dict[str, str] = dict(extra or {})
        if self._team_id:
            # Official docs: team API requests must include teamID parameter.
            params.setdefault("teamID", self._team_id)
        return params

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        content: bytes | None = None,
        base_url: str | None = None,
    ) -> httpx.Response:
        root = (base_url or self._base_url).rstrip("/")
        url = f"{root}{path if path.startswith('/') else '/' + path}"
        headers = self._headers()
        if json is not None and files is None:
            headers = {**headers, "Content-Type": "application/json"}
        try:
            with httpx.Client(
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    params=self._params(params) or None,
                    json=json,
                    files=files,
                    content=content,
                )
        except httpx.TimeoutException as exc:
            logger.warning("Liara request timeout method=%s path=%s", method, path)
            raise LiaraTimeoutError("Liara API request timed out") from exc
        except httpx.RequestError as exc:
            logger.warning(
                "Liara network error method=%s path=%s err=%s",
                method,
                path,
                sanitize_for_log(str(exc)),
            )
            raise LiaraHttpError(f"Liara network error: {sanitize_for_log(str(exc))}") from exc

        self._raise_for_status(response, method=method, path=path)
        return response

    def _raise_for_status(
        self, response: httpx.Response, *, method: str, path: str
    ) -> None:
        status = response.status_code
        if status < 400:
            return
        body_safe = sanitize_for_log(response.text)
        logger.warning(
            "Liara HTTP error method=%s path=%s status=%s body=%s",
            method,
            path,
            status,
            body_safe,
        )
        if status == 401:
            raise LiaraUnauthorizedError(
                "Liara authentication failed", status_code=401
            )
        if status == 403:
            raise LiaraForbiddenError("Liara access forbidden", status_code=403)
        if status == 404:
            raise LiaraNotFoundError("Liara resource not found", status_code=404)
        if status == 429:
            raise LiaraRateLimitError("Liara rate limit exceeded", status_code=429)
        raise LiaraHttpError(
            f"Liara HTTP {status}",
            status_code=status,
        )

    def get_me(self) -> dict[str, Any]:
        """GET /v1/me — account/console info (docs.liara.ir/references/api/get-info/)."""
        response = self.request("GET", "/v1/me")
        data = response.json()
        if not isinstance(data, dict):
            raise LiaraHttpError("Unexpected /v1/me response shape")
        return data

    def list_projects(self) -> list[dict[str, Any]]:
        """GET /v1/projects — list apps owned by the authenticated account."""
        response = self.request("GET", "/v1/projects")
        data = response.json()
        if isinstance(data, list):
            return [p for p in data if isinstance(p, dict)]
        if isinstance(data, dict):
            projects = data.get("projects", [])
            if isinstance(projects, list):
                return [p for p in projects if isinstance(p, dict)]
        raise LiaraHttpError("Unexpected /v1/projects response shape")

    def prove_read_access(self) -> ProveReadResult:
        """Live read proof: me + projects. Does not enable write tools."""
        me = self.get_me()
        projects = self.list_projects()
        return ProveReadResult(
            me=_public_me_summary(me),
            projects=_public_project_summaries(projects),
            project_count=len(projects),
        )

    def get_project(self, name: str) -> dict[str, Any]:
        """GET /v1/projects/{name} — app details for reconcile."""
        response = self.request("GET", f"/v1/projects/{name}")
        data = response.json()
        if isinstance(data, dict):
            project = data.get("project")
            if isinstance(project, dict):
                return project
            if "project_id" in data or "name" in data or "_id" in data:
                return data
        raise LiaraHttpError("Unexpected GET project response shape")

    def list_releases(self, name: str) -> dict[str, Any]:
        """GET /v1/projects/{name}/releases — release list for verify/reconcile."""
        response = self.request("GET", f"/v1/projects/{name}/releases")
        data = response.json()
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {"releases": data, "total": len(data)}
        raise LiaraHttpError("Unexpected GET releases response shape")

    # --- Phase 3 evidence reads (logs / events / metrics) ----------------------

    def get_logs(self, name: str) -> list[dict[str, Any]]:
        """GET /v1/projects/{name}/logs — runtime/build log lines (sanitize before LLM)."""
        response = self.request("GET", f"/v1/projects/{name}/logs")
        data = response.json()
        if isinstance(data, list):
            return [e for e in data if isinstance(e, dict)]
        if isinstance(data, dict):
            logs = data.get("logs") or data.get("data") or []
            if isinstance(logs, list):
                return [e for e in logs if isinstance(e, dict)]
        raise LiaraHttpError("Unexpected GET logs response shape")

    def get_events(self, name: str) -> list[dict[str, Any]]:
        """GET /v1/projects/{name}/events — app lifecycle events."""
        response = self.request("GET", f"/v1/projects/{name}/events")
        data = response.json()
        if isinstance(data, list):
            return [e for e in data if isinstance(e, dict)]
        if isinstance(data, dict):
            events = data.get("events") or data.get("data") or []
            if isinstance(events, list):
                return [e for e in events if isinstance(e, dict)]
        raise LiaraHttpError("Unexpected GET events response shape")

    def get_cpu_metrics(self, name: str) -> dict[str, Any] | list[Any] | None:
        """GET /v1/projects/{name}/metrics/cpu — may be missing; callers record gaps."""
        response = self.request("GET", f"/v1/projects/{name}/metrics/cpu")
        if not response.content:
            return None
        data = response.json()
        if isinstance(data, (dict, list)):
            return data
        return None

    def get_memory_metrics(self, name: str) -> dict[str, Any] | list[Any] | None:
        """GET /v1/projects/{name}/metrics/memory — may be missing; callers record gaps."""
        response = self.request("GET", f"/v1/projects/{name}/metrics/memory")
        if not response.content:
            return None
        data = response.json()
        if isinstance(data, (dict, list)):
            return data
        return None

    def create_project(
        self,
        *,
        name: str,
        plan_id: str,
        platform: str,
        read_only_root_filesystem: bool = True,
        network: str | None = None,
    ) -> dict[str, Any]:
        """POST /v1/projects — create app (developers.liara.ir create-a-app)."""
        body: dict[str, Any] = {
            "name": name,
            "planID": plan_id,
            "platform": platform,
            "readOnlyRootFilesystem": read_only_root_filesystem,
        }
        if network:
            body["network"] = network
        response = self.request("POST", "/v1/projects", json=body)
        # Docs: 200 may have empty body; treat name as provider id.
        if not response.content:
            return {"project_name": name, "status_code": response.status_code}
        try:
            data = response.json()
        except ValueError:
            return {"project_name": name, "status_code": response.status_code}
        if isinstance(data, dict):
            return {**data, "project_name": name}
        return {"project_name": name, "raw": data}

    def upload_source(
        self,
        *,
        project_name: str,
        archive_path: str | Path,
    ) -> dict[str, Any]:
        """POST /v2/projects/{name}/sources — multipart .gz → sourceID."""
        path = Path(archive_path)
        if not path.is_file():
            raise LiaraHttpError(f"source archive not found: {path.name}")
        with path.open("rb") as handle:
            files = {"file": (path.name, handle, "application/gzip")}
            response = self.request(
                "POST",
                f"/v2/projects/{project_name}/sources",
                files=files,
            )
        data = response.json()
        if not isinstance(data, dict) or "sourceID" not in data:
            raise LiaraHttpError("Unexpected sources response — missing sourceID")
        return {"sourceID": data["sourceID"], "project_name": project_name}

    def create_release(
        self,
        *,
        project_name: str,
        source_id: str,
        port: int,
        platform: str,
    ) -> dict[str, Any]:
        """POST /v2/projects/{name}/releases — sourceID + port + type → releaseID."""
        body = {
            "sourceID": source_id,
            "port": port,
            "type": platform,
        }
        response = self.request(
            "POST",
            f"/v2/projects/{project_name}/releases",
            json=body,
        )
        data = response.json()
        if not isinstance(data, dict) or "releaseID" not in data:
            raise LiaraHttpError("Unexpected releases response — missing releaseID")
        return {
            "releaseID": data["releaseID"],
            "project_name": project_name,
            "sourceID": source_id,
        }

    # --- Phase 2 ops (env / restart / resize / domains / SSL / DNS) -------------

    def project_envs(self, name: str) -> list[dict[str, Any]]:
        """Read env keys from GET /v1/projects/{name} (values may be present; callers redact)."""
        project = self.get_project(name)
        envs = project.get("envs")
        if not isinstance(envs, list):
            return []
        return [e for e in envs if isinstance(e, dict)]

    def update_envs(
        self,
        *,
        project: str,
        variables: list[dict[str, str]],
    ) -> dict[str, Any]:
        """POST /v1/projects/update-envs — OpenAPI has no merge/replace mode (L-D03)."""
        body = {"project": project, "variables": variables}
        response = self.request("POST", "/v1/projects/update-envs", json=body)
        if not response.content:
            return {"project": project, "status_code": response.status_code, "message": "ok"}
        try:
            data = response.json()
        except ValueError:
            return {"project": project, "status_code": response.status_code}
        if isinstance(data, dict):
            return {**data, "project": project}
        return {"project": project, "raw": data}

    def restart_project(self, name: str) -> dict[str, Any]:
        """POST /v1/projects/{name}/actions/restart — acceptance ≠ healthy."""
        response = self.request("POST", f"/v1/projects/{name}/actions/restart")
        return {
            "project_name": name,
            "status_code": response.status_code,
            "restart_accepted": response.status_code < 400,
        }

    def resize_project(self, name: str, *, plan_id: str) -> dict[str, Any]:
        """POST /v1/projects/{name}/resize — planID required; cost unknown unless priced."""
        response = self.request(
            "POST",
            f"/v1/projects/{name}/resize",
            json={"planID": plan_id},
        )
        return {
            "project_name": name,
            "planID": plan_id,
            "status_code": response.status_code,
            "resize_accepted": response.status_code < 400,
            "cost_known": False,
            "cost_summary": "unknown",
        }

    def list_domains(self, *, project: str) -> list[dict[str, Any]]:
        """GET /v1/domains?project= — domains for an app."""
        response = self.request("GET", "/v1/domains", params={"project": project})
        data = response.json()
        if isinstance(data, dict):
            domains = data.get("domains", [])
            if isinstance(domains, list):
                return [d for d in domains if isinstance(d, dict)]
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
        raise LiaraHttpError("Unexpected GET domains response shape")

    def create_domain(
        self,
        *,
        name: str,
        project: str,
        domain_type: str = "PROJECT",
    ) -> dict[str, Any]:
        """POST /v1/domains — returns domain._id on 201."""
        body = {"name": name, "project": project, "type": domain_type}
        response = self.request("POST", "/v1/domains", json=body)
        if not response.content:
            return {
                "domain_name": name,
                "project": project,
                "status_code": response.status_code,
            }
        data = response.json()
        domain_id = None
        if isinstance(data, dict):
            domain = data.get("domain")
            if isinstance(domain, dict):
                domain_id = domain.get("_id")
            domain_id = domain_id or data.get("_id") or data.get("domainID")
        return {
            "domain_id": domain_id,
            "domain_name": name,
            "project": project,
            "status_code": response.status_code,
        }

    def set_domain_project(
        self, *, domain_id: str, project_id: str
    ) -> dict[str, Any]:
        """POST /v1/domains/set-project."""
        response = self.request(
            "POST",
            "/v1/domains/set-project",
            json={"domainID": domain_id, "projectID": project_id},
        )
        return {
            "domain_id": domain_id,
            "project_id": project_id,
            "status_code": response.status_code,
            "set_project_accepted": response.status_code < 400,
        }

    def check_domain(self, domain_id: str) -> dict[str, Any]:
        """GET /v1/domains/{id}/check — status + certificatesStatus."""
        response = self.request("GET", f"/v1/domains/{domain_id}/check")
        data = response.json()
        domain: dict[str, Any] = {}
        if isinstance(data, dict):
            inner = data.get("domain")
            if isinstance(inner, dict):
                domain = inner
            else:
                domain = data
        return {
            "domain_id": domain.get("_id") or domain_id,
            "name": domain.get("name"),
            "status": domain.get("status"),
            "certificatesStatus": domain.get("certificatesStatus"),
            "CNameRecord": domain.get("CNameRecord"),
            "raw_keys": sorted(domain.keys()),
        }

    def provision_ssl(self, *, domain: str) -> dict[str, Any]:
        """POST /v1/domains/provision-ssl-certs — request accepted ≠ cert valid."""
        response = self.request(
            "POST",
            "/v1/domains/provision-ssl-certs",
            json={"domain": domain},
        )
        payload: dict[str, Any] = {
            "domain": domain,
            "status_code": response.status_code,
            "ssl_request_accepted": response.status_code < 400,
            "cert_valid": False,  # never infer validity from acceptance alone
        }
        if response.content:
            try:
                data = response.json()
                if isinstance(data, dict):
                    payload["provider_code"] = data.get("code")
            except ValueError:
                pass
        return payload

    def list_databases(self) -> list[dict[str, Any]]:
        """GET /v1/databases — DBaaS list (developers.liara.ir DBaaS OpenAPI)."""
        response = self.request("GET", "/v1/databases")
        data = response.json()
        if isinstance(data, dict):
            databases = data.get("databases", [])
            if isinstance(databases, list):
                return [d for d in databases if isinstance(d, dict)]
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
        raise LiaraHttpError("Unexpected GET /v1/databases response shape")

    def get_database(self, database_id: str) -> dict[str, Any]:
        """GET /v1/databases/{id} — may include node.root_password; never log it."""
        response = self.request("GET", f"/v1/databases/{database_id}")
        data = response.json()
        if not isinstance(data, dict):
            raise LiaraHttpError("Unexpected GET database response shape")
        return data

    def create_database(
        self,
        *,
        hostname: str,
        db_type: str,
        plan_id: str,
        version: str,
        public_network: bool = False,
        standalone_replica_set: bool | None = None,
    ) -> dict[str, Any]:
        """POST /v1/databases — returns databaseID. Live use requires registry enabled."""
        body: dict[str, Any] = {
            "hostname": hostname,
            "type": db_type,
            "planID": plan_id,
            "version": version,
            "publicNetwork": public_network,
        }
        if standalone_replica_set is not None:
            body["options"] = {"standaloneReplicaSet": standalone_replica_set}
        response = self.request("POST", "/v1/databases", json=body)
        out: dict[str, Any] = {
            "hostname": hostname,
            "type": db_type,
            "planID": plan_id,
            "version": version,
            "status_code": response.status_code,
        }
        if response.content:
            try:
                data = response.json()
                if isinstance(data, dict):
                    out["databaseID"] = data.get("databaseID") or data.get("id")
            except ValueError:
                pass
        return out

    def list_disks(self, project_name: str) -> list[dict[str, Any]]:
        """GET /v1/projects/{id}/disks — disks for an app."""
        response = self.request("GET", f"/v1/projects/{project_name}/disks")
        data = response.json()
        if isinstance(data, dict):
            disks = data.get("disks", [])
            if isinstance(disks, list):
                return [d for d in disks if isinstance(d, dict)]
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
        raise LiaraHttpError("Unexpected GET disks response shape")

    def create_disk(
        self,
        *,
        project_name: str,
        name: str,
        size: str,
    ) -> dict[str, Any]:
        """POST /v1/projects/{name}/disks — body name + size (string GB)."""
        response = self.request(
            "POST",
            f"/v1/projects/{project_name}/disks",
            json={"name": name, "size": str(size)},
        )
        return {
            "project_name": project_name,
            "name": name,
            "size": str(size),
            "status_code": response.status_code,
            "disk_created": response.status_code < 400,
        }

    def list_dns_zones(self) -> list[dict[str, Any]]:
        """GET {dns}/api/v1/zones — zones owned by the account."""
        response = self.request(
            "GET", "/api/v1/zones", base_url=self._dns_base_url
        )
        data = response.json()
        if isinstance(data, dict):
            zones = data.get("zones") or data.get("data") or []
            if isinstance(zones, list):
                return [z for z in zones if isinstance(z, dict)]
            # Some responses nest under status/data
            if isinstance(data.get("data"), dict):
                nested = data["data"].get("zones")
                if isinstance(nested, list):
                    return [z for z in nested if isinstance(z, dict)]
        if isinstance(data, list):
            return [z for z in data if isinstance(z, dict)]
        raise LiaraHttpError("Unexpected GET DNS zones response shape")

    def create_dns_record(
        self,
        *,
        zone: str,
        name: str,
        record_type: str,
        contents: list[dict[str, Any]],
        ttl: int | None = 3600,
    ) -> dict[str, Any]:
        """POST {dns}/api/v1/zones/{zone}/dns-records — only for owned zones."""
        body: dict[str, Any] = {
            "name": name,
            "type": record_type,
            "contents": contents,
        }
        if ttl is not None:
            body["ttl"] = ttl
        response = self.request(
            "POST",
            f"/api/v1/zones/{zone}/dns-records",
            json=body,
            base_url=self._dns_base_url,
        )
        out: dict[str, Any] = {
            "zone": zone,
            "name": name,
            "type": record_type,
            "status_code": response.status_code,
        }
        if response.content:
            try:
                data = response.json()
                if isinstance(data, dict):
                    record = data.get("data") if isinstance(data.get("data"), dict) else data
                    if isinstance(record, dict):
                        out["record_id"] = record.get("id")
            except ValueError:
                pass
        return out


def _public_me_summary(me: dict[str, Any]) -> dict[str, Any]:
    """Strip potentially sensitive nested fields from /v1/me for API responses."""
    user = me.get("user") if isinstance(me.get("user"), dict) else {}
    account = me.get("account") if isinstance(me.get("account"), dict) else {}
    return {
        "has_user": bool(user or account or me),
        "email": user.get("email") or account.get("email") or me.get("email"),
        "name": user.get("name") or account.get("name") or me.get("name"),
        "keys": sorted(k for k in me.keys() if k != "token"),
    }


def _public_project_summaries(
    projects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for project in projects[:50]:
        summaries.append(
            {
                "project_id": project.get("project_id") or project.get("name"),
                "type": project.get("type"),
                "status": project.get("status"),
                "isDeployed": project.get("isDeployed"),
            }
        )
    return summaries

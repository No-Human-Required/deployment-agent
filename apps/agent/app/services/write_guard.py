"""Allowlisted write boundary — model output never calls this directly.

Slice 05: Liara create_project / sources / releases behind approval.
Slice 07: restart / resize / domains / ssl / dns records (not update_envs).
Tests spy on calls to assert schema/approval failures make zero provider HTTP.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.services.liara_client import LiaraClient, LiaraClientError

# Registry-aligned allowlist (deploy + ops + phase-4 deps). update_envs intentionally excluded.
DEPLOY_WRITE_TOOLS = frozenset({"create_project", "sources", "releases"})
OPS_WRITE_TOOLS = frozenset(
    {
        "restart",
        "resize",
        "create_domain",
        "set_domain_project",
        "provision_ssl",
        "dns_create_record",
    }
)
DEP_WRITE_TOOLS = frozenset({"create_database", "create_disk"})
ALLOWLISTED_WRITE_TOOLS = DEPLOY_WRITE_TOOLS | OPS_WRITE_TOOLS | DEP_WRITE_TOOLS


class ProviderWrite(Protocol):
    def __call__(
        self, *, tool_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None: ...


class WriteNotAllowlisted(ValueError):
    def __init__(self, tool_id: str) -> None:
        super().__init__(f"tool not allowlisted for write: {tool_id}")
        self.tool_id = tool_id


def noop_provider_write(*, tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Default when no Liara client — records intent only (no HTTP)."""
    _ = (tool_id, payload)
    return {"mode": "noop", "provider_write": False}


class LiaraProviderWrite:
    """Maps allowlisted tool_ids to LiaraClient write methods."""

    def __init__(self, client: LiaraClient) -> None:
        self._client = client

    def __call__(
        self, *, tool_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if tool_id == "create_project":
            return self._client.create_project(
                name=str(payload["name"]),
                plan_id=str(payload.get("planID") or payload.get("plan_id")),
                platform=str(payload.get("platform") or "node"),
                read_only_root_filesystem=bool(
                    payload.get("readOnlyRootFilesystem", True)
                ),
                network=payload.get("network"),
            )
        if tool_id == "sources":
            return self._client.upload_source(
                project_name=str(payload["project_name"]),
                archive_path=str(payload["archive_path"]),
            )
        if tool_id == "releases":
            return self._client.create_release(
                project_name=str(payload["project_name"]),
                source_id=str(payload.get("sourceID") or payload.get("source_id")),
                port=int(payload["port"]),
                platform=str(payload.get("type") or payload.get("platform") or "node"),
            )
        if tool_id == "restart":
            return self._client.restart_project(str(payload["project_name"]))
        if tool_id == "resize":
            return self._client.resize_project(
                str(payload["project_name"]),
                plan_id=str(payload.get("planID") or payload.get("plan_id")),
            )
        if tool_id == "create_domain":
            return self._client.create_domain(
                name=str(payload["name"]),
                project=str(payload["project"]),
                domain_type=str(payload.get("type") or "PROJECT"),
            )
        if tool_id == "set_domain_project":
            return self._client.set_domain_project(
                domain_id=str(payload.get("domain_id") or payload.get("domainID")),
                project_id=str(payload.get("project_id") or payload.get("projectID")),
            )
        if tool_id == "provision_ssl":
            return self._client.provision_ssl(domain=str(payload["domain"]))
        if tool_id == "dns_create_record":
            return self._client.create_dns_record(
                zone=str(payload["zone"]),
                name=str(payload["name"]),
                record_type=str(payload.get("type") or payload.get("record_type")),
                contents=list(payload.get("contents") or []),
                ttl=int(payload["ttl"]) if payload.get("ttl") is not None else 3600,
            )
        if tool_id == "create_database":
            return self._client.create_database(
                hostname=str(payload["hostname"]),
                db_type=str(payload.get("type") or payload.get("db_type")),
                plan_id=str(payload.get("planID") or payload.get("plan_id")),
                version=str(payload["version"]),
                public_network=bool(payload.get("publicNetwork", False)),
                standalone_replica_set=(
                    bool(payload["standaloneReplicaSet"])
                    if payload.get("standaloneReplicaSet") is not None
                    else None
                ),
            )
        if tool_id == "create_disk":
            return self._client.create_disk(
                project_name=str(payload["project_name"]),
                name=str(payload["name"]),
                size=str(payload["size"]),
            )
        raise WriteNotAllowlisted(tool_id)


class WriteGuard:
    """Single chokepoint for provider-side mutations."""

    def __init__(
        self,
        provider_write: ProviderWrite | None = None,
        *,
        liara_client: LiaraClient | None = None,
    ) -> None:
        if provider_write is not None:
            self._provider_write = provider_write
        elif liara_client is not None:
            self._provider_write = LiaraProviderWrite(liara_client)
        else:
            self._provider_write = noop_provider_write
        self.call_count = 0
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.http_call_count = 0  # incremented only by LiaraProviderWrite path via spy

    def execute_allowlisted(
        self, *, tool_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if tool_id not in ALLOWLISTED_WRITE_TOOLS:
            raise WriteNotAllowlisted(tool_id)
        self.call_count += 1
        self.calls.append((tool_id, payload))
        try:
            result = self._provider_write(tool_id=tool_id, payload=payload) or {}
        except LiaraClientError:
            raise
        if isinstance(self._provider_write, LiaraProviderWrite):
            self.http_call_count += 1
        return dict(result)

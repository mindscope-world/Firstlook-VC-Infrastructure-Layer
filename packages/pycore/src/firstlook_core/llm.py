"""Client for the LLM gateway (services/gateway).

Application code never calls model providers directly: every request goes
through the gateway, which enforces per-tenant budgets, redaction, metering,
audit logging and tracing, and picks the model for the task.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

import httpx

from .config import get_settings
from .embeddings import hash_embed


@dataclass
class StructuredResult:
    data: dict[str, Any]
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class BudgetExceeded(RuntimeError):
    pass


class LlmClient(Protocol):
    def structured(
        self,
        tenant_id: UUID | str,
        task: str,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = 16000,
    ) -> StructuredResult: ...

    def embed(self, tenant_id: UUID | str, texts: list[str], task: str = "embed") -> list[list[float]]: ...


class GatewayClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 600.0):
        s = get_settings()
        self._http = httpx.Client(
            base_url=base_url or s.gateway_url,
            headers={"Authorization": f"Bearer {token or s.internal_service_token}"},
            timeout=timeout,
        )

    def structured(self, tenant_id, task, *, system, user, schema, max_tokens=16000) -> StructuredResult:
        r = self._http.post(
            "/v1/structured",
            headers={"X-Tenant-Id": str(tenant_id)},
            json={"task": task, "system": system, "user": user, "schema": schema, "max_tokens": max_tokens},
        )
        if r.status_code == 402:
            raise BudgetExceeded(r.json().get("detail", "LLM budget exceeded"))
        r.raise_for_status()
        body = r.json()
        return StructuredResult(
            body["data"], body["model"], body.get("input_tokens", 0), body.get("output_tokens", 0)
        )

    def embed(self, tenant_id, texts, task="embed") -> list[list[float]]:
        r = self._http.post(
            "/v1/embeddings", headers={"X-Tenant-Id": str(tenant_id)}, json={"task": task, "input": texts}
        )
        if r.status_code == 402:
            raise BudgetExceeded(r.json().get("detail", "LLM budget exceeded"))
        r.raise_for_status()
        return r.json()["embeddings"]


@dataclass
class FakeLlm:
    """Deterministic stand-in for tests and offline seeding.

    responder(task, system, user, schema) -> dict supplies structured output;
    embeddings use the local hash embedder.
    """

    responder: Any = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def structured(self, tenant_id, task, *, system, user, schema, max_tokens=16000) -> StructuredResult:
        self.calls.append({"tenant_id": str(tenant_id), "task": task, "system": system, "user": user})
        data = self.responder(task, system, user, schema) if self.responder else {}
        return StructuredResult(data, "fake")

    def embed(self, tenant_id, texts, task="embed") -> list[list[float]]:
        return [hash_embed(t) for t in texts]


_client: LlmClient | None = None


def get_llm() -> LlmClient:
    global _client
    if _client is None:
        _client = GatewayClient()
    return _client


def set_llm(client: LlmClient | None) -> None:
    """Override the process-wide client (tests, offline seeding)."""
    global _client
    _client = client

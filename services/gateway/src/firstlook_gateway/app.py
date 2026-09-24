"""Gateway HTTP API (internal only; callers present the internal service token).

POST /v1/structured   JSON-schema output for a task
POST /v1/embeddings   embeddings for a batch of texts

Every call: checks the tenant's monthly budget, redacts the prompt, routes to
a provider, records usage, stores the full prompt/response in the tenant's
raw zone, and writes an audit event pointing at it.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from firstlook_core import audit
from firstlook_core.auth import verify_internal_token
from firstlook_core.db import tenant_tx
from firstlook_core.objects import TenantObjects

from .providers import AnthropicProvider, LiteLLMProvider, OfflineProvider, ProviderError, local_embed
from .redaction import redact
from .routing import cost_usd, route_for
from .tracing import trace_generation

app = FastAPI(title="Firstlook LLM gateway")

_providers: dict[str, Any] = {}


def provider(name: str) -> Any:
    if name not in _providers:
        _providers[name] = {
            "anthropic": AnthropicProvider,
            "litellm": LiteLLMProvider,
            "offline": OfflineProvider,
        }[name]()
    return _providers[name]


def _caller_tenant(
    authorization: Annotated[str | None, Header()] = None,
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> UUID:
    token = authorization.removeprefix("Bearer ") if authorization else None
    if not verify_internal_token(token):
        raise HTTPException(401, "invalid service token")
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-Id is required")
    try:
        return UUID(x_tenant_id)
    except ValueError as e:
        raise HTTPException(400, "X-Tenant-Id must be a UUID") from e


CallerTenant = Annotated[UUID, Depends(_caller_tenant)]


class StructuredRequest(BaseModel):
    task: str = Field(pattern=r"^[a-z0-9_.-]+$")
    system: str
    user: str
    schema_: dict[str, Any] = Field(alias="schema")
    max_tokens: int = Field(default=16000, ge=1, le=64000)
    redact: bool = True


class EmbedRequest(BaseModel):
    task: str = "embed"
    input: list[str] = Field(max_length=512)


def _check_budget(tenant_id: UUID) -> None:
    with tenant_tx(tenant_id) as conn:
        row = conn.execute(
            "SELECT b.monthly_limit_usd AS lim, coalesce(sum(u.cost_usd), 0) AS spent"
            " FROM llm_budgets b LEFT JOIN llm_usage u ON u.tenant_id = b.tenant_id"
            "   AND u.created_at >= date_trunc('month', now())"
            " WHERE b.tenant_id = %s GROUP BY b.monthly_limit_usd",
            (str(tenant_id),),
        ).fetchone()
    if row is None:
        raise HTTPException(403, "tenant has no LLM budget configured")
    if Decimal(row["spent"]) >= Decimal(row["lim"]):
        raise HTTPException(402, f"monthly LLM budget of ${row['lim']} reached")


def _record(
    tenant_id: UUID,
    *,
    task: str,
    provider_name: str,
    model: str,
    request_id: str | None,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    status: str,
    transcript: dict[str, Any] | None,
) -> None:
    with tenant_tx(tenant_id) as conn:
        uri = None
        if transcript is not None:
            body = json.dumps(
                {**transcript, "at": datetime.now(UTC).isoformat(), "id": str(uuid.uuid4())}, default=str
            ).encode()
            uri = TenantObjects(conn, tenant_id).put("llm", body, "application/json", ".json")
        conn.execute(
            "INSERT INTO llm_usage (tenant_id, request_id, task, provider, model, input_tokens, output_tokens,"
            " cost_usd, latency_ms, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                str(tenant_id),
                request_id,
                task,
                provider_name,
                model,
                input_tokens,
                output_tokens,
                cost_usd(model, input_tokens, output_tokens),
                latency_ms,
                status,
            ),
        )
        audit.record(
            conn,
            tenant_id,
            "llm.call",
            "llm_task",
            task,
            actor_type="service",
            details={
                "provider": provider_name,
                "model": model,
                "status": status,
                "transcript_uri": uri,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/structured")
def structured(req: StructuredRequest, tenant_id: CallerTenant) -> dict[str, Any]:
    _check_budget(tenant_id)
    route = route_for(req.task, "structured")
    user, redactions = redact(req.user) if req.redact else (req.user, {})
    started = datetime.now(UTC)
    t0 = time.monotonic()
    try:
        result = provider(route.provider).structured(
            route.model, req.system, user, req.schema_, req.max_tokens
        )
    except ProviderError as e:
        _record(
            tenant_id,
            task=req.task,
            provider_name=route.provider,
            model=route.model,
            request_id=None,
            input_tokens=0,
            output_tokens=0,
            latency_ms=int((time.monotonic() - t0) * 1000),
            status=f"error:{e.status}",
            transcript=None,
        )
        raise HTTPException(e.status, str(e)) from e
    latency = int((time.monotonic() - t0) * 1000)
    _record(
        tenant_id,
        task=req.task,
        provider_name=route.provider,
        model=result.model,
        request_id=result.request_id,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=latency,
        status="ok",
        transcript={"system": req.system, "user": user, "redactions": redactions, "output": result.data},
    )
    trace_generation(
        tenant_id=str(tenant_id),
        task=req.task,
        model=result.model,
        input={"system": req.system, "user": user},
        output=result.data,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        started=started,
        ended=datetime.now(UTC),
    )
    return {
        "data": result.data,
        "model": result.model,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "redactions": redactions,
    }


@app.post("/v1/embeddings")
def embeddings(req: EmbedRequest, tenant_id: CallerTenant) -> dict[str, Any]:
    route = route_for(req.task, "embed")
    if route.provider == "local":
        return {"embeddings": local_embed(req.input), "model": "local:hash-1024"}
    _check_budget(tenant_id)
    t0 = time.monotonic()
    try:
        vectors, tokens = provider(route.provider).embed(route.model, req.input)
    except ProviderError as e:
        raise HTTPException(e.status, str(e)) from e
    _record(
        tenant_id,
        task=req.task,
        provider_name=route.provider,
        model=route.model,
        request_id=None,
        input_tokens=tokens,
        output_tokens=0,
        latency_ms=int((time.monotonic() - t0) * 1000),
        status="ok",
        transcript=None,
    )
    return {"embeddings": vectors, "model": route.model}

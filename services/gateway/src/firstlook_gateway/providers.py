"""Provider adapters behind the gateway."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

from firstlook_core.embeddings import hash_embed


@dataclass
class Completion:
    data: dict[str, Any]
    model: str
    input_tokens: int
    output_tokens: int
    request_id: str | None = None


class ProviderError(RuntimeError):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


class AnthropicProvider:
    """Claude via the official Anthropic SDK with structured outputs.

    Uses the server-side refusal fallback ("default" mode) so a declined
    request is retried on Anthropic's recommended fallback model.
    """

    def __init__(self) -> None:
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.Anthropic()

    def structured(
        self, model: str, system: str, user: str, schema: dict[str, Any], max_tokens: int
    ) -> Completion:
        a = self._anthropic
        try:
            response = self._client.beta.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
                betas=["server-side-fallback-2026-07-01"],
                extra_body={"fallbacks": "default"},
            )
        except a.RateLimitError as e:
            raise ProviderError(f"rate limited: {e}", 429) from e
        except a.BadRequestError as e:
            raise ProviderError(f"bad request: {e}", 400) from e
        except a.APIStatusError as e:
            raise ProviderError(f"provider error {e.status_code}: {e}", 502) from e
        except a.APIConnectionError as e:
            raise ProviderError(f"provider unreachable: {e}", 503) from e

        if response.stop_reason == "refusal":
            raise ProviderError("model declined the request", 422)
        if response.stop_reason == "max_tokens":
            raise ProviderError("output truncated at max_tokens", 502)
        text = "".join(b.text for b in response.content if b.type == "text")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ProviderError(f"model returned invalid JSON: {e}") from e
        return Completion(
            data,
            response.model,
            response.usage.input_tokens,
            response.usage.output_tokens,
            getattr(response, "_request_id", None),
        )


class LiteLLMProvider:
    """Non-Claude models and hosted embeddings via the LiteLLM proxy."""

    def __init__(self) -> None:
        self._http = httpx.Client(
            base_url=os.environ.get("LITELLM_URL", "http://localhost:14000"),
            headers={"Authorization": f"Bearer {os.environ.get('LITELLM_MASTER_KEY', 'sk-local')}"},
            timeout=600,
        )

    def structured(
        self, model: str, system: str, user: str, schema: dict[str, Any], max_tokens: int
    ) -> Completion:
        r = self._http.post(
            "/v1/chat/completions",
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "output", "schema": schema, "strict": True},
                },
            },
        )
        if r.status_code >= 400:
            raise ProviderError(f"litellm {r.status_code}: {r.text[:500]}", 502)
        body = r.json()
        usage = body.get("usage", {})
        return Completion(
            json.loads(body["choices"][0]["message"]["content"]),
            body.get("model", model),
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
            body.get("id"),
        )

    def embed(self, model: str, texts: list[str]) -> tuple[list[list[float]], int]:
        r = self._http.post("/v1/embeddings", json={"model": model, "input": texts, "dimensions": 1024})
        if r.status_code >= 400:
            raise ProviderError(f"litellm {r.status_code}: {r.text[:500]}", 502)
        body = r.json()
        return [d["embedding"] for d in body["data"]], body.get("usage", {}).get("prompt_tokens", 0)


class OfflineProvider:
    """No credentials configured: return an empty object that satisfies the
    schema's required arrays, so pipelines run end to end without a model."""

    def structured(
        self, model: str, system: str, user: str, schema: dict[str, Any], max_tokens: int
    ) -> Completion:
        return Completion(_empty_for(schema), "offline", 0, 0)


def _empty_for(schema: dict[str, Any]) -> Any:
    t = schema.get("type")
    if t == "object":
        return {
            k: _empty_for(v)
            for k, v in schema.get("properties", {}).items()
            if k in schema.get("required", [])
        }
    if t == "array":
        return []
    if t == "string":
        return ""
    if t in ("number", "integer"):
        return 0
    if t == "boolean":
        return False
    return None


def local_embed(texts: list[str]) -> list[list[float]]:
    return [hash_embed(t) for t in texts]

"""Which provider and model serve each task.

Defaults can be overridden per task with GATEWAY_ROUTE_<TASK>=provider:model,
e.g. GATEWAY_ROUTE_EXTRACT_INTERACTION=litellm:gpt-default. Tenants that bring
their own key get ANTHROPIC_API_KEY swapped per tenant in Phase 3.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# USD per million tokens (input, output). Keep in sync with provider pricing.
PRICING = {
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

DEFAULT_STRUCTURED = "anthropic:claude-opus-5"
DEFAULT_EMBED = "local:hash-1024"


@dataclass(frozen=True)
class Route:
    provider: str  # anthropic, litellm, local, offline
    model: str


def _parse(spec: str) -> Route:
    provider, _, model = spec.partition(":")
    return Route(provider, model)


def route_for(task: str, kind: str) -> Route:
    override = os.environ.get(f"GATEWAY_ROUTE_{task.upper().replace('.', '_').replace('-', '_')}")
    if override:
        return _parse(override)
    if kind == "embed":
        return _parse(os.environ.get("GATEWAY_EMBED_DEFAULT", DEFAULT_EMBED))
    default = os.environ.get("GATEWAY_STRUCTURED_DEFAULT", DEFAULT_STRUCTURED)
    route = _parse(default)
    # Without Anthropic credentials, fall back to offline so local dev works.
    if route.provider == "anthropic" and not (
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    ):
        return Route("offline", "offline")
    return route


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICING.get(model, (0.0, 0.0))
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000

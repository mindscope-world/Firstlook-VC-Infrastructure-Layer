# 0005. LLM gateway

Status: accepted · 2026-09-25

**Decision.** All model calls go through `services/gateway`. For each call it checks the tenant's monthly budget (HTTP 402 when exceeded), redacts payment cards, bank accounts, government IDs and credentials from prompts (names and emails are kept because the tasks need them), routes the task to a provider, meters tokens and cost into `llm_usage`, stores the full prompt and response encrypted in the tenant's object store, writes an audit event, and traces to Langfuse when configured.

- Claude is called through the official Anthropic SDK, using structured outputs (`output_config.format` with a JSON schema) and server-side refusal fallback (`fallbacks: "default"`). The default model is `claude-opus-5`, overridable per task with `GATEWAY_ROUTE_<TASK>`.
- Other providers and hosted embeddings go through the LiteLLM proxy.
- With no credentials, an offline provider returns schema-valid empty output, so pipelines run without a key. Entity-resolution embeddings default to a local hash embedder.

**Consequences.** Application code depends only on `firstlook_core.llm.LlmClient`. Swapping models is a routing change, and every prompt is auditable.

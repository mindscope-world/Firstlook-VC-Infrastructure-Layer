# Firstlook

Relationship intelligence for venture firms. Firstlook ingests a fund's email, calendar, call transcripts and CRM exports, resolves them into a per-firm knowledge graph, and surfaces relationship strength, warm intro paths, and AI-extracted intros, next steps and deal mentions, each with a citation back to its source. See [plan.md](plan.md) for the roadmap.

## Quick start

Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node 22 and pnpm 10.

```bash
make setup   # .env from .env.example, Python + Node dependencies
make up      # local infrastructure (Docker)
make seed    # two synthetic funds; no API key needed
make dev     # every service with reload
```

Open http://localhost:13000 and sign in as `paul@savanna.vc` (dev login). To run real extraction instead of the fixtures' golden answers, set `ANTHROPIC_API_KEY` in `.env` and run `make seed-llm`. To connect your own mailbox, see [docs/connectors.md](docs/connectors.md).

## Layout

```
apps/marketing        Vite landing page (unchanged)
apps/web              Next.js product UI; proxies /api/* to the services
services/api          TypeScript (Fastify) API: graph, review queue, extractions, deals, Slack command
services/ingest       Python: OAuth connectors, sync, CRM import, Slack install + notifications
services/resolver     Python: MIME parsing, quote/signature stripping, entity resolution, relationship strength
services/ai           Python: cited extraction of intros, next steps, deal mentions
services/gateway      Python: LLM gateway (budgets, redaction, metering, audit; Claude via the Anthropic SDK)
workflows             Temporal workflows (account sync, nightly strength, CRM API import)
packages/pycore       Shared Python: tenant-scoped DB, encryption, adapters, outbox, auth
packages/schema       SQL migrations: tables, row-level security, merge / warm-path / decision functions
packages/fixtures     Synthetic funds, seed script
compose/              Local stack: Postgres+pgvector, Redis, SeaweedFS, Redpanda, Temporal, ClickHouse, LiteLLM, Mailpit
infra/docker          Container images
docs/adr              Architecture decisions
```

## How data flows

```
connector ──▶ raw object (encrypted, S3) + sources row + outbox ──relay──▶ interactions.raw
  ──▶ resolver: parse, strip quotes and signatures, resolve people and companies, relationship strength
      ──▶ outbox ──▶ interactions.resolved
  ──▶ ai: extraction through the gateway, verbatim citations ──▶ proposed extractions
  ──▶ people accept or reject in the Inbox ──▶ graph edges, deals ──▶ deals.events ──▶ Slack
```

Tenant isolation is enforced by Postgres row-level security ([ADR 0003](docs/adr/0003-tenant-isolation.md)).

## Tests

```bash
make up && make test   # Python (pytest) + TypeScript (vitest); DB tests use the firstlook_test database
make lint
```

Ports (local): web 13000, api 14100, ingest 14200, gateway 14300, Postgres 15432, S3 18333, Kafka 19092, Temporal 17233 (UI 18233), ClickHouse 18123, Mailpit 18025, Langfuse 13100, Grafana 13300.

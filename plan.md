# Firstlook: Implementation and Deployment Plan

*Based on "VC Intelligence Infrastructure: Technical Proposal" (Sep 24, 2026). Drafted Sep 24, 2026.*

This plan turns the proposal into a build sequence. **We build the application first and deploy to the cloud last.** Phases 0–3 build and validate the full product on a local, containerised stack with no dependency on any cloud provider. Phase 4 chooses a provider and takes the product to production.

Where the plan differs from the proposal, it says so and gives the reason.

---

## 1. Where we are today

- This repo holds the **marketing site** only: Vite + React 19 + Tailwind 4, with an Express/`@google/genai` server-side hook. It was scaffolded in AI Studio. It keeps its current hosting and is out of scope for this plan.
- None of the platform exists yet: no backend, data layer, connectors or infrastructure.
- `package.json` has uncommitted dependency reordering and an esbuild bump, and `package-lock.json` is untracked. Commit both before the restructure below.

**Consequence:** the first engineering step is to turn this repo into a monorepo. The landing page stays shippable throughout.

---

## 2. Approach: app first, cloud last

**Principle:** everything runs locally with `docker compose up`. Every stateful dependency is an open-source component or sits behind an interface, so any cloud provider can host it later without code changes.

What this means in practice:
- **Portable components only.** Postgres, Redis, S3-compatible object storage, Temporal and ClickHouse all run locally and have managed equivalents on every major cloud.
- **Adapters for anything provider-specific.** Object storage, key management, the event bus, OCR and email delivery each get a small interface with a local implementation now and cloud implementations in Phase 4.
- **12-factor services.** Config comes from environment variables, services keep no local state, logs go to stdout, and every service ships as a container image with a health check. Phase 4 then only has to package and operate the services, not change them.
- **Continuous integration from day one, continuous deployment in Phase 4.** GitHub Actions runs tests, isolation checks and evals on every PR. Nothing is deployed until Phase 4.

**Trade-off to accept:** the proposal has design-partner funds using the product from month 3. Real customer mailboxes and documents can't be processed on laptops, so design partners **can only see demos** until Phase 4 unless we set up an early hosted pilot (see §12, question 1). Before then, validation uses synthetic data, the team's own mailboxes (Google and Microsoft test-mode OAuth allows this on `localhost`), and design partners reviewing demos on anonymised data.

---

## 3. Technology choices (provider-neutral)

| Area | Choice | Local dev | Why |
|---|---|---|---|
| Product frontend | **Next.js (App Router) + TypeScript + Tailwind** | `next dev` | As proposed. The Vite marketing site stays a separate app. |
| App API | **TypeScript (Fastify or NestJS) + GraphQL (Pothos/Yoga) + REST** | container | Shared types with the frontend |
| AI / data services | **Python 3.12 + FastAPI**, `uv` for packaging | container | ML ecosystem |
| OLTP + graph + vectors | **Postgres 16 + pgvector**; graph as `entities` / `edges` tables with recursive CTEs | `pgvector/pgvector` image | One database to secure and audit. Add Apache AGE or a graph DB only if traversal queries measurably hurt. |
| Analytics warehouse | **ClickHouse** | `clickhouse/clickhouse-server` | As proposed. Runs locally and self-hosted or managed anywhere. |
| Cache / rate limits | **Redis** | `redis` | Standard |
| Object storage | **S3 API** via a storage adapter | **MinIO** | Every cloud offers an S3-compatible or adaptable store |
| Workflows / agents | **Temporal** | `temporal server start-dev` | Durable retries for ingestion, backfills and multi-step agents |
| Event bus | **Kafka API** via a bus adapter | **Redpanda** (single node) | Kafka-compatible, so it maps to any managed Kafka later. Postgres outbox pattern for transactional publishing. |
| Tenant isolation | **Shared schema + `tenant_id` + Postgres Row-Level Security + per-tenant data keys** | same | *Deviation from the proposal's per-tenant schemas.* Schema-per-tenant multiplies migration and connection-pool pain. RLS plus envelope encryption gives equivalent logical isolation and is auditable. |
| Key management | **KMS adapter** (envelope encryption) | local master key or **OpenBao/Vault** dev server | Swapped for the chosen cloud's KMS in Phase 4 |
| LLM gateway | **LiteLLM proxy** behind our own thin service (tenant metering, PII redaction, audit log) | container | Model-agnostic, bring-your-own-key, cost caps per tenant |
| OCR / parsing | **Unstructured / Docling + Tesseract**, with LLM vision as a fallback | container | No cloud OCR lock-in |
| Auth | **WorkOS** (SSO SAML/OIDC, SCIM) or Auth0, behind an auth adapter | dev tenant | Enterprise SSO is a sales gate. Don't build it. These are SaaS, not tied to a cloud. |
| Observability | **OpenTelemetry**, **Langfuse** (LLM traces), Sentry | Grafana LGTM + Langfuse containers | As proposed. Choose hosted versions in Phase 4. |
| Product analytics | **PostHog** | container or cloud | Needed to measure the success metrics |
| CI | **GitHub Actions** | — | Tests, evals and security scans. No deploy step until Phase 4. |

---

## 4. Repository layout (target)

Monorepo managed with **pnpm workspaces + Turborepo** for TypeScript and **uv workspaces** for Python.

```
firstlook/
├── apps/
│   ├── marketing/          # current Vite landing site (moved as-is)
│   ├── web/                # Next.js product app
│   └── founder-portal/     # KPI portal (phase 2; may be a route group in web)
├── services/
│   ├── api/                # TS: GraphQL + REST + webhooks, authz
│   ├── ingest/             # Py: connector workers (Gmail, Graph, Zoom, WhatsApp, Drive…)
│   ├── resolver/           # Py: parsing, OCR, entity resolution, enrichment
│   ├── ai/                 # Py: RAG, extraction, memo generation, agents
│   ├── gateway/            # LiteLLM config + metering/redaction sidecar
│   ├── ranker/             # Py: thesis scoring (XGBoost) + LLM re-rank
│   └── mcp/                # MCP server over the graph (phase 3)
├── workflows/              # Temporal workflow + activity definitions (Py)
├── packages/
│   ├── schema/             # canonical data model: SQL migrations, generated TS/Py types
│   ├── adapters/           # storage, bus, kms, ocr, email interfaces + local impls
│   ├── ui/                 # shared React components
│   ├── evals/              # golden datasets + eval harness
│   └── fixtures/           # synthetic funds, people, companies, decks, KPIs
├── compose/                # docker-compose.yml + seed scripts for the full local stack
├── infra/                  # empty until Phase 4 (IaC for the chosen cloud)
└── docs/                   # ADRs, runbooks, threat model, data-flow diagrams
```

Migrations use **Atlas** or **sqitch** in `packages/schema`. Types for TS and Python are generated from one source so the two stacks can't drift.

---

## 5. Core data model (first cut)

Define this in Phase 0. Every module depends on it.

- **Tenancy & access:** `tenants`, `users`, `roles`, `memberships`, `deal_teams`, `acl_grants`
- **Entities:** `people`, `companies`, `funds`, `deals`, `rounds`, `documents`, `interactions` (email/meeting/call/message)
- **Graph:** `entities(id, tenant_id, type, canonical_key)` + `edges(src, dst, type, props, source_ref, confidence, valid_from, valid_to)`
- **Identity:** `identifiers(entity_id, kind: email|domain|registry_id|linkedin|phone, value)` is the backbone of entity resolution
- **Provenance:** `sources(raw_object_uri, connector, fetched_at, hash)`. Every fact and edge carries a `source_ref`, which makes the proposal's "citations by default" enforceable at the schema level.
- **AI outputs:** `extractions`, `scores`, `memos`, `agent_runs`, `approvals` (human-in-the-loop state)
- **Portfolio:** `kpi_definitions`, `kpi_submissions`, `kpi_values(normalised_value, currency, fx_rate_ref)`
- **Audit:** append-only `audit_events`, also streamed to ClickHouse

Retrieval chunks (`chunks(id, tenant_id, source_ref, acl_hash, embedding vector)`) carry ACL metadata, so RAG filters by permission *in the query* rather than after it.

---

## 6. Phased build plan

Durations are indicative. Phases 0–3 build the application. Phase 4 deploys it.

### Phase 0: Foundations (Months 0–2)

**Goal:** a developer can run the whole stack locally, connect their own Gmail or Outlook account, and see interactions resolved into a tenant-isolated graph.

Status as of 2026-09-25 (branch `phase-0-foundations`): `[x]` means built and tested in the repo, `[~]` means partly done, `[ ]` means not started. The notes say what is left.

Week 1–2 (setup)
- [x] Commit the pending `package.json`/lockfile. Restructure into the monorepo (`apps/marketing`). Confirm the marketing site still builds.
- [x] Write ADRs for every choice in §3 (`docs/adr/0001`–`0006`).
- [~] Set up the GitHub org: branch protection, CODEOWNERS, Renovate, secret scanning, CI skeleton (lint, typecheck, test, build, container scan). *CODEOWNERS, Renovate and CI (including gitleaks and Trivy) are in the repo. Branch protection, org secret scanning and real team handles in CODEOWNERS are GitHub settings someone must apply.*
- [x] `compose/docker-compose.yml` with Postgres+pgvector, Redis, S3 storage, Redpanda, Temporal, ClickHouse, LiteLLM, Langfuse, and Grafana/OTel. Add `make dev` and `make seed`. *SeaweedFS replaces MinIO, which no longer publishes images (ADR 0004).*
- [ ] Start **long-lead external processes** that don't need production infrastructure (see §8): data-vendor quotes, design-partner agreements, model-vendor zero-data-retention terms. *Business tasks; not code.*

Weeks 3–8 (build)
- [x] `packages/schema` v1 with RLS policies and tests proving that tenant A cannot read tenant B.
- [x] Adapters (in `firstlook_core.adapters`): storage, bus, KMS (envelope encryption with per-tenant data keys), OCR, email. Each has a local implementation and a contract test suite that later cloud implementations must also pass.
- [~] Auth: WorkOS dev environment + Google/Microsoft login, RBAC, deal-level ACLs in `services/api`. *Dev login, RBAC and deal-level/private ACLs are done and tested. The WorkOS AuthKit flow is written but untested against a real WorkOS environment.*
- [x] Ingestion framework: connector interface (`auth → backfill → incremental sync`), raw-to-object-store-to-bus event contract (transactional outbox), Temporal workflows for backfill with rate-limit-aware retries. *Push webhooks are not built; sync polls every 5 minutes.*
- [~] Connectors: **Gmail + Google Calendar**, **Microsoft Graph mail + calendar**, using test-mode OAuth apps. Mailbox/label selection UI with personal-email exclusion by default. *Tested against mocked provider APIs only. Not yet run against a real mailbox: that needs OAuth client IDs in `.env` (docs/connectors.md).*
- [x] LLM gateway: per-tenant budgets, request/response audit logging, PII redaction, Langfuse tracing. Claude runs through the Anthropic SDK with LiteLLM for other providers (ADR 0005).
- [~] `packages/fixtures`: a synthetic fund with people, companies, email threads, a deck, meetings, a transcript and CRM exports. *KPIs are left for Phase 2.*
- [x] Minimal `apps/web`: login, connect accounts, synced interactions and people (plus the 1a screens below).

**Exit gate:** `make dev && make seed` brings up a working stack on a clean machine. A team member's own mailbox syncs into the graph. The RLS isolation suite is green in CI. *Seed, the stack and RLS tests work locally. The real-mailbox check and a first CI run on GitHub are still to do.*

---

### Phase 1: MVP features (Months 3–6)

**Goal:** the three MVP modules work end to end on synthetic data and the team's own data, and design partners have validated them through demos.

**1a. Relationship intelligence (auto-CRM)**
- [x] Parser pipeline: MIME/HTML cleanup, signature and quoted-thread stripping, attachment extraction (stored encrypted), signature enrichment of titles.
- [x] Entity resolution v1: deterministic rules (email, domain, registry ID, CRM ID), then embedding + name similarity with confidence scores. Low-confidence matches go to a **review queue UI** (merge / distinct).
- [x] LLM extraction of intros, next steps and deal mentions using JSON-schema outputs, with validation and verbatim citations back to message IDs and character offsets. Accepting an item is what writes to the graph (ADR 0006). *Only checked against golden fixture output. It has not yet run against a live model with an eval score (`make seed-llm` is the entry point).*
- [x] Relationship strength score (recency, frequency, reciprocity), plus team-wide "warm path" queries over `edges` (`warm_paths()` in SQL).
- [~] Zoom/Meet transcript connector. CRM migration importers: **Affinity, HubSpot, Salesforce, Airtable** (CSV + API). *CSV import is tested. API importers and transcript connectors are tested only against mocked APIs or not at all.*
- [~] Slack app v1 (dev workspace): deal channel notifications, `/firstlook <company>` lookup. *Signature verification and lookup are tested. Not yet installed in a real workspace.*

**1b. Deal sourcing and scoring**
- [ ] Thesis editor: structured filters (sector, stage, geo, cheque size) plus a free-text description, versioned per fund.
- [ ] Signal ingestion from the first licensed data vendor (sandbox/trial access), plus free sources: company registries (incl. Kenya BRS where accessible), news RSS, job boards, GitHub. Daily Temporal schedules write to ClickHouse.
- [ ] Ranker stage 1: rules + embedding similarity to the thesis (cold start). Collect thumbs up/down from day one. Switch to XGBoost once there are about 500 labels per fund or pooled features.
- [ ] Ranker stage 2: LLM re-rank of the top N with a written rationale and citations.
- [ ] Sourcing feed UI + weekly digest.

**1c. Diligence and memo copilot**
- [ ] Document ingestion: upload, Google Drive, Dropbox, DocSend. PDF/PPTX/XLSX parsing, with OCR for scanned files.
- [ ] Fact-sheet extraction schema (team, traction, unit economics, round terms) with per-field confidence and source spans.
- [ ] Consistency checks (e.g. deck ARR vs model ARR) shown as flags.
- [ ] Memo drafting in the firm's own template (tenant-uploaded template → section prompts), with a citation for every numeric claim. Uncited numbers are highlighted.
- [ ] "New inbound deck" workflow (the proposal's sequence diagram) implemented as a Temporal workflow. Output: fact sheet + score + draft reply awaiting analyst approval.

**1d. Quality and safety**
- [ ] `packages/evals`: golden sets per task (entity resolution precision/recall, extraction field accuracy, memo citation coverage, ranking NDCG). Start from public decks and synthetic data. Add design-partner samples later only with consent and after Phase 4 provides a secure place to keep them. Evals run in CI on every prompt or model change, and a regression fails the build.
- [ ] Prompt-injection defences: untrusted content wrapped as data, tool allow-lists per task, no outbound actions without an `approvals` record, red-team test set in evals.
- [ ] Threat model + data-flow diagrams. Secure-by-design review of the auth, RLS and adapter code.

**Exit gate:** on fixtures, deck → fact sheet takes under 15 min and a memo draft takes under 2 h end to end. Entity-resolution precision is at least 95% on the golden set. At least 3 design partners have seen demos and given written feedback.

---

### Phase 2: Portfolio (Months 7–10)

- [ ] **Founder portal** (magic-link auth, per-company KPI forms, file upload), plus email-in and API ingestion.
- [ ] KPI normalisation: metric-name mapping (LLM-suggested, human-confirmed), currency normalisation (KES, NGN, USD, EUR…) with a daily FX source stored as `fx_rate_ref` for auditability.
- [ ] Accounting connectors: **Xero, QuickBooks** (sandbox orgs).
- [ ] Benchmarks vs cohort and plan. Anomaly rules (runway < 6 months, burn spike, missed submission), then statistical detection.
- [ ] Alerts via Slack/Teams/email. Microsoft Teams app. Board-meeting brief generator.
- [ ] Automated KPI chase agent (drafts reminders; sends only with approval or an explicit per-fund auto-send opt-in).
- [ ] **WhatsApp Business** connector (inbound founder messages via the fund's own WABA number; Meta test number during development).
- [ ] Right-to-erasure pipeline: delete propagates through Postgres, vector chunks, ClickHouse and object storage, with a ledger for backup expiry.

**Exit gate:** a synthetic portfolio of 50+ companies reports KPIs through the portal, normalises correctly, and triggers the expected alerts.

---

### Phase 3: Scale features (Months 11–14)

- [ ] **LP reporting:** TVPI/DPI/IRR from portfolio + fund-admin exports, quarterly LP letter drafts, finance review/approval flow, PDF export.
- [ ] **Terms analysis:** term-sheet/SHA parsing, clause library per firm playbook, flags against comparable deals in the firm's own history.
- [ ] **Agents framework:** "research this company", "prep IC brief", "chase missing KPIs". Step limits, cost caps and full audit trail per run.
- [ ] **Public API:** GraphQL + REST with the same authz as the UI, API keys + OAuth clients, webhooks (new deal, score change, KPI alert), rate limits, versioning policy, developer docs.
- [ ] **MCP server** over the tenant graph (OAuth, scoped tools, read-only by default).
- [ ] Bring-your-own model keys. Per-tenant fine-tuning hooks (opt-in only, isolated artifacts).
- [ ] Load and performance testing on the local stack at 20-fund synthetic scale, to size the Phase 4 infrastructure.

**Exit gate:** the full proposal feature set is complete, passes evals, and holds up under a 20-fund synthetic load test.

---

### Phase 4: Cloud deployment and production (Months 15–18)

**Goal:** choose a provider, deploy the finished app, onboard design partners on real data, and begin the compliance track.

**4a. Choose the provider (first 2 weeks)**
- [ ] Compare AWS, GCP, Azure and managed-PaaS options (e.g. Render/Fly plus managed Postgres) on these criteria: regions needed by signed customers (EU, US, Africa), managed Postgres with pgvector, managed Kafka/Temporal/ClickHouse availability, KMS, credits, and any design partner's mandated provider.
- [ ] Record the decision in an ADR.

**4b. Infrastructure**
- [ ] Infrastructure as code (Terraform or OpenTofu) for networking, container runtime (managed Kubernetes or a container service), managed Postgres (HA, point-in-time recovery, customer-managed keys), object storage (versioned, retention-locked raw zone), managed Kafka or Redpanda Cloud, Temporal Cloud, ClickHouse Cloud, KMS keyrings per tenant, secrets manager, WAF + load balancer.
- [ ] Cloud implementations of each `packages/adapters` interface, passing the same contract tests as the local ones.
- [ ] Hosted observability (Grafana Cloud or equivalent), Sentry, Langfuse, alerting + on-call rota, status page.

**4c. Environments and delivery**

| Env | Purpose | Data | Deploy trigger |
|---|---|---|---|
| `staging` | Release candidate, load and eval runs | Synthetic only | Merge to `main` (auto) |
| `prod-<region>` | Customer tenants, one per residency region (EU, US; Africa on demand) | Customer | Tagged release, manual promote |
| `tenant-<name>` | Enterprise single-tenant, from the same IaC module | Customer | Same release train, customer-agreed window |

CI/CD pipeline, extended from the existing CI:
1. **Merge to `main`:** build signed images (cosign), deploy to `staging`, run migrations as a pre-deploy job (expand-only), then smoke + e2e (Playwright) + eval regression.
2. **Release:** tag, then manual approval per prod region. Canary rollout (10% → 50% → 100%) gated on error-rate and latency SLOs, with automatic rollback on breach.
3. **Migrations:** expand/contract only. Destructive changes ship one release after code stops using the old shape.
4. **Infra:** IaC applies from CI only, with required review from the infra CODEOWNER.

**4d. Production readiness and compliance**
- [ ] Google OAuth restricted-scope verification + **CASA** assessment, Microsoft publisher verification, Meta business verification. These need production URLs, so file them as soon as `staging` has stable domains. Expect 6–12 weeks, which sets the earliest date real mailboxes can be connected at scale.
- [ ] Model-vendor zero-data-retention agreements signed before any customer data reaches a model.
- [ ] External penetration test with a focus on cross-tenant access. Close critical and high findings before onboarding.
- [ ] DPIA (GDPR + Kenya Data Protection Act 2019), ODPC registration if needed, DPA, sub-processor list, privacy policy.
- [ ] Onboard Vanta/Drata, then **SOC 2 Type I**, then start the Type II observation window.
- [ ] Reliability targets: 99.9% availability for web/API, email ingestion lag p95 under 2 min, **RPO ≤ 15 min, RTO ≤ 4 h**, restore drill before launch and quarterly after.
- [ ] Onboard 3–5 design partners on real data, then move to paid.

**Exit gate:** design partners are live in production and weekly active. The pen test is clean. The SOC 2 Type I audit has started.

---

## 7. Team and staffing sequence

| Month | Hires / roles active |
|---|---|
| 0 | Tech lead/architect, PM (VC background), product designer, 1 backend/data engineer, 1 full-stack |
| 1–2 | +2 backend/data engineers, +1 ML/AI engineer |
| 7–8 | +data-partnerships lead |
| 12–14 | +security engineer, +SRE/platform engineer (both needed for Phase 4) |
| 15+ | +customer success/solutions for onboarding |

Ownership: the tech lead owns the data model and adapters, backend engineers own connectors, resolver and API, the ML engineer owns gateway, evals, extraction and ranker, full-stack owns web and founder portal. The SRE and security engineer lead Phase 4.

---

## 8. Critical path and long-lead items

These can start before any cloud exists:
1. **Design partners.** Sign 3–5 funds to demo-based feedback now, with a pilot agreement covering data use and eval consent that takes effect once Phase 4 is live.
2. **Data vendor contracts.** Pricing (the most variable COGS line) and licence terms, which must allow per-tenant use and forbid redistribution. Get 3 quotes and sandbox access. Prioritise vendors with African coverage plus local registry partnerships.
3. **Model vendor zero-data-retention terms.** Negotiate early and sign before Phase 4 onboarding.

These can only start in Phase 4, because they need production URLs or infrastructure:
4. **Google OAuth restricted scopes (Gmail read).** App verification + annual CASA assessment, 6–12 weeks. Until approved, the app runs as a testing app capped at 100 users.
5. **Microsoft 365 publisher verification,** plus an admin-consent onboarding flow for funds that require it.
6. **WhatsApp Business Platform.** Meta business verification. Only the fund's own WABA number can be synced, not personal WhatsApp. Set expectations with design partners early.
7. **SOC 2.** Type I in Phase 4 and Type II about 6–12 months later. This is later than the proposal's "Type II within 12 months of launch", so enterprise sales will depend on it after the first paying customers.

---

## 9. Budget checkpoints

- **Phases 0–3:** costs are mainly LLM API usage, data-vendor trials and SaaS tools (WorkOS, Sentry, GitHub). Per-tenant LLM budgets and metering exist in the gateway from Phase 0.
- **Phase 4:** validate against the proposal's run-rate at 20 funds ($18k–57k/month) using the Phase 3 load-test numbers.
- Prompt caching, batch APIs for backfills, and small models for classification/ER keep the LLM line down. Frontier models are reserved for memo drafting and re-ranking.
- Review unit economics (COGS per fund vs planned price) at the end of each phase.

---

## 10. Launch checklist (Phase 4, per production region)

- [ ] IaC applied from CI. Drift detection on.
- [ ] Cloud adapter implementations pass the contract suite.
- [ ] RLS isolation suite + pen test findings closed (critical/high).
- [ ] Backups verified by an actual restore. Runbooks for DB failover, key rotation, connector outage, LLM vendor outage (gateway fallback model).
- [ ] SLO dashboards + alerts routed to on-call. Status page live.
- [ ] DPA, privacy policy, sub-processor list, and a security page on the marketing site (update `SecuritySection.tsx` to match what's actually true).
- [ ] Tenant onboarding runbook: SSO setup, mailbox scope selection, CRM import, thesis setup, eval baseline.
- [ ] Data deletion / offboarding runbook tested end to end.

---

## 11. Success metrics instrumentation

Build product analytics (PostHog) in Phase 1 so the metrics exist when real usage starts in Phase 4:

| Metric | Target | Instrumented via |
|---|---|---|
| Manual CRM entries / analyst / week | −90% | Count of manual record creates vs auto-created |
| Inbound deck → screened fact sheet | < 15 min | Workflow start/end timestamps |
| Funded deals first surfaced by platform | Tracked from first real usage | `first_seen_source` on company + deal outcome |
| KPI on-time submission | > 85% | Submission vs due date |
| WAU / investment staff | > 70% | Auth + event analytics |

---

## 12. Open questions to resolve with stakeholders

1. **Early hosted pilot:** is waiting until Phase 4 (about month 15) for real design-partner usage acceptable? The alternative is a small, hardened hosted pilot for one or two partners in Phase 1, which pulls part of Phase 4 forward.
2. **Isolation model:** confirm RLS + per-tenant keys (recommended) vs schema-per-tenant as written in the proposal.
3. **First data vendor(s)** and budget ceiling for Phases 1–3.
4. **Pricing and packaging** (affects metering design and the enterprise tier).
5. **Which design partners** and which residency regions they'll need. This feeds the Phase 4 provider choice.

---

## 13. Next 10 working days

1. Commit pending changes. Create the monorepo and move the landing site to `apps/marketing`.
2. Write ADRs for §3 and get sign-off on §12 items 1–2.
3. Build `compose/docker-compose.yml` and the CI pipeline (tests only).
4. Create Google and Microsoft test-mode OAuth apps for local connector development.
5. Request data-vendor quotes and sandbox access. Send design-partner feedback agreements.
6. Draft `packages/schema` v1 and the RLS test harness.
7. Define `packages/adapters` interfaces and start the synthetic fixtures.

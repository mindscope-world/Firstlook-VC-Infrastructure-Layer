# 0003. Tenant isolation with row-level security and per-tenant keys

Status: accepted · 2026-09-25 · deviates from the proposal's per-tenant schemas

**Context.** Firms' data must never cross tenants. Schema-per-tenant multiplies migrations and connection pools.

**Decision.**
- One shared schema. Every tenant-owned table has `tenant_id` and `FORCE ROW LEVEL SECURITY`. Services connect as `firstlook_app` (NOBYPASSRLS) and set `app.tenant_id`, `app.user_id` and `app.user_role` with `SET LOCAL` per transaction (`firstlook_core.db.tenant_tx`, `services/api/src/lib/db.ts`).
- Restrictive policies add deal-level restriction (restricted deals visible only to their deal team and admins), private interactions (owner only), and per-user connector accounts.
- Each tenant has a data key wrapped by the KMS adapter. OAuth tokens, Slack tokens, CRM credentials in workflow history, and every raw object are encrypted with it.
- Only schedulers and the outbox relay use `firstlook_system` (BYPASSRLS). The API uses it only to map a login to a tenant.
- A test asserts that every table with a `tenant_id` column has forced RLS, so a new table can't ship without it.

**Consequences.** Isolation is enforced by Postgres even when application code is wrong. Enterprise single-tenant deployments reuse the same code with one tenant.

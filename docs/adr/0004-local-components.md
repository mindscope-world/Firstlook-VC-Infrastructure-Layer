# 0004. Local components

Status: accepted · 2026-09-25

| Need | Choice | Notes |
|---|---|---|
| OLTP, graph, vectors | Postgres 16 + pgvector, `pg_trgm` | Graph = `entities` + `edges`; traversal in SQL (`warm_paths`) |
| Object storage | SeaweedFS (S3 API) | Plan said MinIO; MinIO stopped publishing container images in 2025. Any S3 endpoint works. |
| Event bus | Redpanda (Kafka API) + transactional outbox | Producers write to `outbox` in the same transaction; `firstlook_core.relay` publishes. Consumers are idempotent, and failures go to `<topic>.dlq`. |
| Workflows | Temporal (`start-dev` locally) | Per-account sync workflows, nightly strength recompute, CRM API import |
| Analytics | ClickHouse | Schema in `compose/clickhouse/init`; not yet written to (Phase 1b signals) |
| Migrations | Plain SQL + a small checksummed runner (`firstlook_core.migrate`) | Plan said Atlas/sqitch; not needed yet. TS/Python type generation is deferred. |
| Auth | WorkOS AuthKit + dev login | Shared HS256 session JWT between the TS and Python services |

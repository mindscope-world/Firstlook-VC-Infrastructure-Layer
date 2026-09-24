-- Analytics store for time-series signals and audit mirroring.
CREATE TABLE IF NOT EXISTS firstlook.audit_events
(
    tenant_id     UUID,
    event_id      Int64,
    actor_type    LowCardinality(String),
    actor_id      Nullable(UUID),
    action        LowCardinality(String),
    resource_type LowCardinality(String),
    resource_id   Nullable(String),
    details       String,
    created_at    DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (tenant_id, created_at, event_id);

CREATE TABLE IF NOT EXISTS firstlook.company_signals
(
    tenant_id   UUID,
    company_id  UUID,
    signal      LowCardinality(String),
    value       Float64,
    source      LowCardinality(String),
    observed_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (tenant_id, company_id, signal, observed_at);

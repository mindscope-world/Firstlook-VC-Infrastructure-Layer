-- 0001_core: tenancy, access control, entities, graph, provenance, audit.
--
-- Isolation model (ADR 0003): one shared schema, every tenant-owned row carries
-- tenant_id, and Postgres row-level security enforces isolation. Services
-- connect as firstlook_app (NOBYPASSRLS) and set app.tenant_id / app.user_id /
-- app.user_role per transaction via SET LOCAL. Nothing outside the database
-- decides which tenant's rows a query can see.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Session context helpers ----------------------------------------------------
-- nullif(): after a SET LOCAL transaction ends the setting reverts to '' (not
-- NULL) for the rest of the session, and ''::uuid would raise.

CREATE FUNCTION app_tenant_id() RETURNS uuid
LANGUAGE sql STABLE AS $$ SELECT nullif(current_setting('app.tenant_id', true), '')::uuid $$;

CREATE FUNCTION app_user_id() RETURNS uuid
LANGUAGE sql STABLE AS $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$;

CREATE FUNCTION app_user_role() RETURNS text
LANGUAGE sql STABLE AS $$ SELECT coalesce(nullif(current_setting('app.user_role', true), ''), 'service') $$;

-- Tenancy & access -----------------------------------------------------------

CREATE TABLE tenants (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL,
    slug            text NOT NULL UNIQUE,
    workos_org_id   text UNIQUE,
    -- Per-tenant data encryption key, wrapped by the KMS adapter's master key.
    wrapped_dek     bytea,
    kms_key_ref     text,
    region          text NOT NULL DEFAULT 'local',
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TYPE user_role AS ENUM ('admin', 'partner', 'associate', 'platform', 'finance', 'viewer');

CREATE TABLE users (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email           citext NOT NULL,
    name            text NOT NULL,
    role            user_role NOT NULL DEFAULT 'associate',
    workos_user_id  text,
    person_id       uuid,  -- the user's own node in the graph; FK added below
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, email)
);
CREATE INDEX users_email_idx ON users (email);

-- Entities & graph -----------------------------------------------------------

CREATE TYPE entity_type AS ENUM ('person', 'company', 'fund', 'deal');

CREATE TABLE entities (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    type            entity_type NOT NULL,
    canonical_name  text NOT NULL,
    -- Set when entity resolution merges this entity into another.
    merged_into     uuid REFERENCES entities(id),
    name_embedding  vector(1024),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id)
);
CREATE INDEX entities_tenant_type_idx ON entities (tenant_id, type) WHERE merged_into IS NULL;
CREATE INDEX entities_name_trgm_idx ON entities USING gin (canonical_name gin_trgm_ops);

CREATE TABLE companies (
    id              uuid PRIMARY KEY REFERENCES entities(id) ON DELETE CASCADE,
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            text NOT NULL,
    domain          citext,
    registry_id     text,
    country         text,
    description     text,
    website         text,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX companies_tenant_domain_idx ON companies (tenant_id, domain);

CREATE TABLE people (
    id              uuid PRIMARY KEY REFERENCES entities(id) ON DELETE CASCADE,
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    full_name       text NOT NULL,
    primary_email   citext,
    title           text,
    company_id      uuid REFERENCES companies(id) ON DELETE SET NULL,
    -- True for the fund's own team; relationship strength is computed from
    -- internal people to everyone else.
    is_internal     boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX people_tenant_company_idx ON people (tenant_id, company_id);

ALTER TABLE users ADD CONSTRAINT users_person_fk FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE SET NULL;

CREATE TYPE identifier_kind AS ENUM ('email', 'domain', 'registry_id', 'linkedin', 'phone', 'crm_id', 'slack_id');

-- The backbone of deterministic entity resolution: one identifier value maps
-- to exactly one entity per tenant.
CREATE TABLE identifiers (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    entity_id       uuid NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    kind            identifier_kind NOT NULL,
    value           citext NOT NULL,
    source_id       uuid,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, kind, value)
);
CREATE INDEX identifiers_entity_idx ON identifiers (entity_id);

-- Provenance: every raw object we ingest. Facts and edges point back here,
-- which is what makes "citations by default" enforceable.
CREATE TABLE sources (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    connector       text NOT NULL,
    connector_account_id uuid,
    external_id     text NOT NULL,
    raw_object_uri  text,
    content_hash    text,
    fetched_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, connector, external_id)
);

ALTER TABLE identifiers ADD CONSTRAINT identifiers_source_fk FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL;

CREATE TABLE edges (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    src_id          uuid NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    dst_id          uuid NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    type            text NOT NULL,       -- works_at, knows, introduced, invested_in, ...
    props           jsonb NOT NULL DEFAULT '{}',
    source_id       uuid REFERENCES sources(id) ON DELETE SET NULL,
    confidence      real NOT NULL DEFAULT 1.0,
    valid_from      timestamptz NOT NULL DEFAULT now(),
    valid_to        timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
-- One live edge per (src, dst, type); history is kept by closing valid_to.
CREATE UNIQUE INDEX edges_live_uq ON edges (tenant_id, src_id, dst_id, type) WHERE valid_to IS NULL;
CREATE INDEX edges_src_idx ON edges (tenant_id, src_id, type) WHERE valid_to IS NULL;
CREATE INDEX edges_dst_idx ON edges (tenant_id, dst_id, type) WHERE valid_to IS NULL;

-- Deals & deal-level access --------------------------------------------------

CREATE TABLE deals (
    id              uuid PRIMARY KEY REFERENCES entities(id) ON DELETE CASCADE,
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    company_id      uuid REFERENCES companies(id) ON DELETE SET NULL,
    name            text NOT NULL,
    stage           text NOT NULL DEFAULT 'sourced',
    -- Restricted deals are visible only to their deal team and admins.
    restricted      boolean NOT NULL DEFAULT false,
    round_size_usd  numeric,
    created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE deal_team_members (
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    deal_id         uuid NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (deal_id, user_id)
);

-- Connectors -----------------------------------------------------------------

CREATE TABLE connector_accounts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider        text NOT NULL,   -- google, microsoft, zoom, slack, hubspot, ...
    account_email   citext,
    scopes          text[] NOT NULL DEFAULT '{}',
    -- OAuth tokens, envelope-encrypted with the tenant's data key.
    encrypted_tokens bytea,
    -- e.g. {"labels": ["INBOX"], "exclude_personal": true}
    settings        jsonb NOT NULL DEFAULT '{"exclude_personal": true}',
    sync_cursor     jsonb NOT NULL DEFAULT '{}',
    status          text NOT NULL DEFAULT 'active',  -- active, paused, error, revoked
    last_error      text,
    last_synced_at  timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, provider, account_email)
);

ALTER TABLE sources ADD CONSTRAINT sources_connector_account_fk
    FOREIGN KEY (connector_account_id) REFERENCES connector_accounts(id) ON DELETE SET NULL;

-- Interactions ---------------------------------------------------------------

CREATE TYPE interaction_kind AS ENUM ('email', 'meeting', 'call', 'message', 'transcript', 'note');

CREATE TABLE interactions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source_id       uuid REFERENCES sources(id) ON DELETE SET NULL,
    kind            interaction_kind NOT NULL,
    external_id     text NOT NULL,       -- Message-ID, calendar event id, ...
    thread_id       text,
    subject         text,
    occurred_at     timestamptz NOT NULL,
    body_text       text,                -- cleaned: quotes and signatures stripped
    body_full_text  text,                -- full plain text, for reference
    signature       text,
    direction       text,                -- inbound, outbound, internal
    owner_user_id   uuid REFERENCES users(id) ON DELETE SET NULL,
    -- private interactions are visible only to their owner.
    visibility      text NOT NULL DEFAULT 'team' CHECK (visibility IN ('team', 'private')),
    deal_id         uuid REFERENCES deals(id) ON DELETE SET NULL,
    metadata        jsonb NOT NULL DEFAULT '{}',
    processed_at    timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, kind, external_id)
);
CREATE INDEX interactions_tenant_time_idx ON interactions (tenant_id, occurred_at DESC);
CREATE INDEX interactions_thread_idx ON interactions (tenant_id, thread_id);

CREATE TABLE interaction_participants (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    interaction_id  uuid NOT NULL REFERENCES interactions(id) ON DELETE CASCADE,
    person_id       uuid REFERENCES people(id) ON DELETE SET NULL,
    email           citext,
    display_name    text,
    role            text NOT NULL   -- from, to, cc, bcc, organizer, attendee, speaker
);
CREATE INDEX participants_interaction_idx ON interaction_participants (interaction_id);
CREATE INDEX participants_person_idx ON interaction_participants (tenant_id, person_id);

CREATE TABLE attachments (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    interaction_id  uuid NOT NULL REFERENCES interactions(id) ON DELETE CASCADE,
    filename        text,
    content_type    text,
    size_bytes      bigint,
    sha256          text NOT NULL,
    object_uri      text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX attachments_interaction_idx ON attachments (interaction_id);

-- Retrieval chunks carry visibility so RAG filters by permission in the query.
CREATE TABLE chunks (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source_id       uuid REFERENCES sources(id) ON DELETE CASCADE,
    interaction_id  uuid REFERENCES interactions(id) ON DELETE CASCADE,
    ordinal         int NOT NULL DEFAULT 0,
    text            text NOT NULL,
    embedding       vector(1024),
    owner_user_id   uuid,
    visibility      text NOT NULL DEFAULT 'team',
    deal_id         uuid,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_interaction_idx ON chunks (interaction_id);

-- Entity resolution review queue ---------------------------------------------

CREATE TABLE er_candidates (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    entity_type     entity_type NOT NULL,
    -- The unresolved mention: {"name", "email", "domain", "context"}
    mention         jsonb NOT NULL,
    -- The provisional entity created for the mention so ingestion can proceed.
    provisional_entity_id uuid REFERENCES entities(id) ON DELETE CASCADE,
    candidate_entity_id   uuid NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    score           real NOT NULL,
    features        jsonb NOT NULL DEFAULT '{}',
    source_id       uuid REFERENCES sources(id) ON DELETE SET NULL,
    status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'merged', 'distinct')),
    decided_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    decided_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX er_candidates_pending_idx ON er_candidates (tenant_id, created_at) WHERE status = 'pending';
CREATE UNIQUE INDEX er_candidates_pair_uq ON er_candidates (tenant_id, provisional_entity_id, candidate_entity_id);

-- AI outputs & human-in-the-loop ----------------------------------------------

CREATE TABLE extractions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    interaction_id  uuid NOT NULL REFERENCES interactions(id) ON DELETE CASCADE,
    kind            text NOT NULL CHECK (kind IN ('intro', 'next_step', 'deal_mention')),
    payload         jsonb NOT NULL,
    -- [{"interaction_id", "external_id", "quote", "start", "end"}]
    citations       jsonb NOT NULL,
    confidence      real NOT NULL,
    model           text NOT NULL,
    prompt_version  text NOT NULL,
    status          text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'accepted', 'rejected', 'done')),
    decided_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    decided_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX extractions_tenant_status_idx ON extractions (tenant_id, status, created_at DESC);
CREATE INDEX extractions_interaction_idx ON extractions (interaction_id);

CREATE TABLE approvals (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    subject_type    text NOT NULL,
    subject_id      uuid NOT NULL,
    action          text NOT NULL,
    status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    requested_by    text NOT NULL,
    decided_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    decided_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- LLM metering ---------------------------------------------------------------

CREATE TABLE llm_budgets (
    tenant_id           uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    monthly_limit_usd   numeric NOT NULL DEFAULT 200
);

CREATE TABLE llm_usage (
    id              bigserial PRIMARY KEY,
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    request_id      text,
    task            text NOT NULL,
    provider        text NOT NULL,
    model           text NOT NULL,
    input_tokens    int NOT NULL DEFAULT 0,
    output_tokens   int NOT NULL DEFAULT 0,
    cost_usd        numeric NOT NULL DEFAULT 0,
    latency_ms      int,
    status          text NOT NULL DEFAULT 'ok',
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX llm_usage_tenant_month_idx ON llm_usage (tenant_id, created_at);

-- Integrations ---------------------------------------------------------------

CREATE TABLE slack_installations (
    tenant_id       uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    team_id         text NOT NULL UNIQUE,
    team_name       text,
    encrypted_bot_token bytea NOT NULL,
    deal_channel_id text,
    installed_by    uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Transactional outbox: rows written in the same transaction as the change,
-- relayed to the event bus by the outbox relay.
CREATE TABLE outbox (
    id              bigserial PRIMARY KEY,
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    topic           text NOT NULL,
    key             text,
    payload         jsonb NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    published_at    timestamptz
);
CREATE INDEX outbox_unpublished_idx ON outbox (id) WHERE published_at IS NULL;

-- Audit ----------------------------------------------------------------------

CREATE TABLE audit_events (
    id              bigserial PRIMARY KEY,
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    actor_type      text NOT NULL,      -- user, service, agent, system
    actor_id        uuid,
    action          text NOT NULL,
    resource_type   text NOT NULL,
    resource_id     text,
    details         jsonb NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_events_tenant_time_idx ON audit_events (tenant_id, created_at DESC);

CREATE FUNCTION audit_events_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only';
END $$;

CREATE TRIGGER audit_events_no_update BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_append_only();

-- Row-level security ---------------------------------------------------------

DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'users', 'entities', 'companies', 'people', 'identifiers', 'sources', 'edges',
        'deals', 'deal_team_members', 'connector_accounts', 'interactions',
        'interaction_participants', 'attachments', 'chunks', 'er_candidates',
        'extractions', 'approvals', 'llm_budgets', 'llm_usage', 'slack_installations',
        'outbox', 'audit_events'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I USING (tenant_id = app_tenant_id()) WITH CHECK (tenant_id = app_tenant_id())',
            t);
    END LOOP;
END $$;

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tenants USING (id = app_tenant_id());

-- Deal-level restriction, layered on top of tenant isolation (policies of the
-- same command are OR-ed, so this one is RESTRICTIVE).
CREATE FUNCTION can_see_deal(p_deal_id uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT p_deal_id IS NULL
        OR app_user_role() IN ('admin', 'service')
        OR EXISTS (SELECT 1 FROM deals d
                   WHERE d.id = p_deal_id AND d.tenant_id = app_tenant_id() AND NOT d.restricted)
        OR EXISTS (SELECT 1 FROM deal_team_members m
                   WHERE m.deal_id = p_deal_id AND m.user_id = app_user_id())
$$;

-- On deals itself the check reads the row's own columns, so it also works for
-- INSERT (can_see_deal would look the new row up before it exists).
CREATE POLICY deal_restriction ON deals AS RESTRICTIVE
    USING (NOT restricted
           OR app_user_role() IN ('admin', 'service')
           OR EXISTS (SELECT 1 FROM deal_team_members m WHERE m.deal_id = deals.id AND m.user_id = app_user_id()))
    WITH CHECK (true);
CREATE POLICY deal_restriction ON interactions AS RESTRICTIVE
    USING (can_see_deal(deal_id));
CREATE POLICY deal_restriction ON chunks AS RESTRICTIVE
    USING (can_see_deal(deal_id));

-- Private interactions are visible only to their owner (services see all).
CREATE POLICY private_visibility ON interactions AS RESTRICTIVE
    USING (visibility = 'team' OR owner_user_id = app_user_id() OR app_user_role() = 'service');
CREATE POLICY private_visibility ON chunks AS RESTRICTIVE
    USING (visibility = 'team' OR owner_user_id = app_user_id() OR app_user_role() = 'service');

-- Connector tokens belong to the user who connected them.
CREATE POLICY own_connectors ON connector_accounts AS RESTRICTIVE
    USING (user_id = app_user_id() OR app_user_role() IN ('admin', 'service'));

-- Grants ---------------------------------------------------------------------

GRANT USAGE ON SCHEMA public TO firstlook_app, firstlook_system;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO firstlook_app, firstlook_system;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO firstlook_app, firstlook_system;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO firstlook_app, firstlook_system;
-- Audit rows can only be appended.
REVOKE UPDATE, DELETE ON audit_events FROM firstlook_app, firstlook_system;

-- Tables, sequences and functions created by later migrations inherit grants.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO firstlook_app, firstlook_system;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO firstlook_app, firstlook_system;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO firstlook_app, firstlook_system;

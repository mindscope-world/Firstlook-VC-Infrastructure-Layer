-- 0005_sourcing: investment theses, company signals, ranking and feedback.

-- Company attributes used for thesis matching. Filled by data vendors,
-- registries and signals; all nullable because coverage varies by source.
ALTER TABLE companies
    ADD COLUMN sectors            text[] NOT NULL DEFAULT '{}',
    ADD COLUMN stage              text,           -- pre-seed, seed, series-a, ...
    ADD COLUMN founded_year       int,
    ADD COLUMN headcount          int,
    ADD COLUMN total_raised_usd   numeric,
    ADD COLUMN last_round_usd     numeric,
    ADD COLUMN last_round_at      date,
    ADD COLUMN github_org         text,
    ADD COLUMN jobs_board         text,           -- "greenhouse:<token>" | "lever:<company>"
    ADD COLUMN description_embedding vector(1024),
    ADD COLUMN profile_source_id  uuid REFERENCES sources(id) ON DELETE SET NULL,
    ADD COLUMN profile_updated_at timestamptz;

-- Theses ----------------------------------------------------------------------
-- A thesis is edited by creating a new version; scores and feedback point at
-- the version they were made against, so history stays interpretable.

CREATE TABLE theses (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            text NOT NULL,
    active          boolean NOT NULL DEFAULT true,
    created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE thesis_versions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    thesis_id       uuid NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    version         int NOT NULL,
    sectors         text[] NOT NULL DEFAULT '{}',
    stages          text[] NOT NULL DEFAULT '{}',
    geographies     text[] NOT NULL DEFAULT '{}',  -- ISO country codes or regions (east-africa, ...)
    cheque_min_usd  numeric,
    cheque_max_usd  numeric,
    founder_profile text NOT NULL DEFAULT '',
    description     text NOT NULL DEFAULT '',
    embedding       vector(1024),
    created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (thesis_id, version)
);

CREATE VIEW current_thesis_versions WITH (security_invoker = true) AS
SELECT DISTINCT ON (v.thesis_id) v.*, t.name, t.active
  FROM thesis_versions v JOIN theses t ON t.id = v.thesis_id
 ORDER BY v.thesis_id, v.version DESC;

-- Signals ---------------------------------------------------------------------
-- Time series of observations per company. Postgres keeps what ranking reads;
-- the same rows are mirrored to ClickHouse (company_signals) for analytics.

CREATE TABLE signal_observations (
    id              bigserial PRIMARY KEY,
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    company_id      uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    signal          text NOT NULL,        -- github_stars, open_roles, news_mention, funding_round_usd, ...
    value           double precision NOT NULL,
    source          text NOT NULL,        -- github, greenhouse, lever, rss:<feed>, vendor:<name>, registry:<name>
    source_id       uuid REFERENCES sources(id) ON DELETE SET NULL,
    url             text NOT NULL DEFAULT '',
    detail          jsonb NOT NULL DEFAULT '{}',
    observed_at     timestamptz NOT NULL DEFAULT now(),
    observed_on     date NOT NULL DEFAULT (now() AT TIME ZONE 'UTC')::date
);
CREATE INDEX signal_obs_company_idx ON signal_observations (tenant_id, company_id, signal, observed_at DESC);
-- One observation per company, signal, source, day and URL keeps daily runs idempotent.
CREATE UNIQUE INDEX signal_obs_daily_uq ON signal_observations (tenant_id, company_id, signal, source, observed_on, url);

-- Ranking ---------------------------------------------------------------------

CREATE TABLE score_runs (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    thesis_version_id   uuid NOT NULL REFERENCES thesis_versions(id) ON DELETE CASCADE,
    ranker              text NOT NULL,     -- rules-v1 | learned:<model id>
    rerank_model        text,
    status              text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'done', 'failed')),
    candidates          int NOT NULL DEFAULT 0,
    scored              int NOT NULL DEFAULT 0,
    reranked            int NOT NULL DEFAULT 0,
    error               text,
    started_at          timestamptz NOT NULL DEFAULT now(),
    finished_at         timestamptz
);
CREATE INDEX score_runs_latest_idx ON score_runs (tenant_id, thesis_version_id, started_at DESC);

CREATE TABLE company_scores (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    run_id              uuid NOT NULL REFERENCES score_runs(id) ON DELETE CASCADE,
    thesis_version_id   uuid NOT NULL REFERENCES thesis_versions(id) ON DELETE CASCADE,
    company_id          uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    stage1_score        real NOT NULL,
    features            jsonb NOT NULL,
    stage2_score        real,             -- 0..1, from the LLM re-rank (top N only)
    final_score         real NOT NULL,
    rationale           text,
    concerns            text,
    citations           jsonb NOT NULL DEFAULT '[]',  -- [{fact_id, kind, label, url, source_id}]
    rank                int NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, company_id)
);
CREATE INDEX company_scores_run_idx ON company_scores (run_id, rank);

-- Thumbs up/down from the sourcing feed: training labels for the ranker.
CREATE TABLE sourcing_feedback (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    thesis_id           uuid NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    thesis_version_id   uuid NOT NULL REFERENCES thesis_versions(id) ON DELETE CASCADE,
    company_id          uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id             uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vote                smallint NOT NULL CHECK (vote IN (-1, 1)),
    reason              text,
    features            jsonb NOT NULL DEFAULT '{}',  -- features at the time of the vote
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (thesis_id, company_id, user_id)
);

-- Learned ranker weights per thesis (once enough labels exist).
CREATE TABLE ranker_models (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    thesis_id           uuid NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    kind                text NOT NULL,    -- logistic-v1 (xgboost later, plan §6 1b)
    weights             jsonb NOT NULL,
    labels              int NOT NULL,
    metrics             jsonb NOT NULL DEFAULT '{}',
    created_at          timestamptz NOT NULL DEFAULT now()
);

DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['theses', 'thesis_versions', 'signal_observations', 'score_runs', 'company_scores',
                             'sourcing_feedback', 'ranker_models'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I USING (tenant_id = app_tenant_id()) WITH CHECK (tenant_id = app_tenant_id())',
            t);
    END LOOP;
END $$;

GRANT SELECT ON current_thesis_versions TO firstlook_app, firstlook_system;

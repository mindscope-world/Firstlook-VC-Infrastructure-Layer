-- 0008_documents: diligence documents (decks, financial models) and the fact
-- sheets extracted from them.
--
-- A document is stored once per tenant (by content hash), encrypted in object
-- storage like every raw object. Parsing turns it into pages (PDF pages,
-- slides, spreadsheet sheets) whose text is what fact sheets cite. Fact sheets
-- are proposals (ADR 0006): a person accepts or rejects them.

CREATE TABLE documents (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    origin          text NOT NULL CHECK (origin IN ('upload', 'email_attachment', 'google_drive', 'dropbox', 'docsend')),
    source_id       uuid REFERENCES sources(id) ON DELETE SET NULL,
    interaction_id  uuid REFERENCES interactions(id) ON DELETE SET NULL,
    attachment_id   uuid REFERENCES attachments(id) ON DELETE SET NULL,
    company_id      uuid REFERENCES companies(id) ON DELETE SET NULL,
    deal_id         uuid REFERENCES deals(id) ON DELETE SET NULL,
    filename        text NOT NULL,
    content_type    text NOT NULL,
    format          text,                -- pdf, pptx, xlsx, image, text
    size_bytes      bigint NOT NULL,
    sha256          text NOT NULL,
    object_uri      text NOT NULL,
    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'parsed', 'failed', 'unsupported')),
    error           text,
    page_count      int,
    ocr_pages       int NOT NULL DEFAULT 0,
    warnings        text[] NOT NULL DEFAULT '{}',
    -- Same visibility rules as the interaction a document arrived with.
    owner_user_id   uuid REFERENCES users(id) ON DELETE SET NULL,
    visibility      text NOT NULL DEFAULT 'team' CHECK (visibility IN ('team', 'private')),
    uploaded_by     uuid REFERENCES users(id) ON DELETE SET NULL,
    parsed_at       timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, sha256)
);
CREATE INDEX documents_company_idx ON documents (tenant_id, company_id, created_at DESC);
CREATE INDEX documents_deal_idx ON documents (tenant_id, deal_id);

-- One row per PDF page, slide or spreadsheet sheet. Citations point at
-- (document_id, page_no) plus character offsets into `text`.
CREATE TABLE document_pages (
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    document_id     uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no         int NOT NULL,        -- 1-based
    kind            text NOT NULL CHECK (kind IN ('page', 'slide', 'sheet', 'image', 'text')),
    title           text,
    text            text NOT NULL,
    ocr             boolean NOT NULL DEFAULT false,
    PRIMARY KEY (document_id, page_no)
);

CREATE TABLE fact_sheets (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    document_id     uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    company_id      uuid REFERENCES companies(id) ON DELETE SET NULL,
    company_name    text,
    -- {"company": {...}, "team": [...], "metrics": [...], "round": {...}}; every
    -- populated field carries a confidence and a citation into document_pages.
    fields          jsonb NOT NULL,
    -- Share of schema fields with a cited value, and how many the validator
    -- dropped because their quote could not be found in the document.
    coverage        real NOT NULL DEFAULT 0,
    dropped_uncited int NOT NULL DEFAULT 0,
    model           text NOT NULL,
    prompt_version  text NOT NULL,
    status          text NOT NULL DEFAULT 'proposed'
                    CHECK (status IN ('proposed', 'accepted', 'rejected', 'superseded')),
    decided_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    decided_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, prompt_version)
);
CREATE INDEX fact_sheets_company_idx ON fact_sheets (tenant_id, company_id, created_at DESC);

-- Row-level security ----------------------------------------------------------

DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['documents', 'document_pages', 'fact_sheets'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I USING (tenant_id = app_tenant_id()) WITH CHECK (tenant_id = app_tenant_id())',
            t);
    END LOOP;
END $$;

CREATE POLICY deal_restriction ON documents AS RESTRICTIVE
    USING (can_see_deal(deal_id));
CREATE POLICY private_visibility ON documents AS RESTRICTIVE
    USING (visibility = 'team' OR owner_user_id = app_user_id() OR app_user_role() = 'service');

-- Pages and fact sheets are visible exactly when their document is (the
-- subquery runs under the documents policies above).
CREATE POLICY document_visible ON document_pages AS RESTRICTIVE
    USING (EXISTS (SELECT 1 FROM documents d WHERE d.id = document_pages.document_id));
CREATE POLICY document_visible ON fact_sheets AS RESTRICTIVE
    USING (EXISTS (SELECT 1 FROM documents d WHERE d.id = fact_sheets.document_id));

-- Decisions -------------------------------------------------------------------
-- Accepting a fact sheet makes it the company's current one (earlier accepted
-- sheets become 'superseded') and fills company profile fields that are still
-- empty. It never overwrites values a person or another source already set.

CREATE FUNCTION decide_fact_sheet(p_sheet uuid, p_decision text, p_user uuid) RETURNS uuid
LANGUAGE plpgsql AS $$
DECLARE
    s fact_sheets;
    v_company uuid;
    v_founded int;
BEGIN
    IF p_decision NOT IN ('accepted', 'rejected') THEN
        RAISE EXCEPTION 'decision must be accepted or rejected';
    END IF;
    SELECT * INTO s FROM fact_sheets WHERE id = p_sheet FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'fact sheet % not found', p_sheet;
    END IF;
    IF s.status <> 'proposed' THEN
        RAISE EXCEPTION 'fact sheet % already decided (%)', p_sheet, s.status;
    END IF;

    UPDATE fact_sheets SET status = p_decision, decided_by = p_user, decided_at = now() WHERE id = p_sheet;

    v_company := coalesce(s.company_id, (SELECT company_id FROM documents WHERE id = s.document_id));
    IF p_decision = 'accepted' AND v_company IS NOT NULL THEN
        UPDATE fact_sheets SET status = 'superseded'
         WHERE company_id = v_company AND status = 'accepted' AND id <> p_sheet;
        UPDATE fact_sheets SET company_id = v_company WHERE id = p_sheet;
        v_founded := CASE WHEN (s.fields #>> '{company,founded_year,value}') ~ '^\d{4}$'
                          THEN (s.fields #>> '{company,founded_year,value}')::int END;
        UPDATE companies SET
            description  = coalesce(description, nullif(s.fields #>> '{company,one_liner,value}', '')),
            founded_year = coalesce(founded_year, v_founded)
         WHERE id = v_company;
    END IF;

    INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, details)
    VALUES (s.tenant_id, 'user', p_user, 'fact_sheet.' || p_decision, 'fact_sheet', p_sheet::text,
            jsonb_build_object('document_id', s.document_id, 'company_id', v_company));
    RETURN p_sheet;
END $$;

-- 0004_extraction_decisions: applying a user's decision on a proposed extraction.
--
-- Extractions are proposals. Accepting one is the human approval that lets it
-- change the graph or CRM:
--   intro        -> `introduced` edges (introducer -> each introduced person,
--                   and between the introduced people), cited to the source
--   deal_mention -> a deal in stage 'sourced' for the (resolved or new) company
--   next_step    -> tracked as an open task (status accepted, later done)
-- Runs as the caller, so row-level security confines it to one tenant.

CREATE FUNCTION person_by_email(p_email text) RETURNS uuid
LANGUAGE sql STABLE AS $$
    SELECT coalesce(e.merged_into, e.id)
      FROM identifiers i JOIN entities e ON e.id = i.entity_id
     WHERE i.kind = 'email' AND i.value = lower(p_email) AND e.type = 'person'
     LIMIT 1
$$;

CREATE FUNCTION decide_extraction(p_extraction uuid, p_decision text, p_user uuid) RETURNS uuid
LANGUAGE plpgsql AS $$
DECLARE
    x extractions;
    v_source uuid;
    v_introducer uuid;
    v_people uuid[] := '{}';
    v_person uuid;
    v_other uuid;
    v_company uuid;
    v_domain text;
    v_deal uuid;
    item jsonb;
BEGIN
    IF p_decision NOT IN ('accepted', 'rejected', 'done') THEN
        RAISE EXCEPTION 'decision must be accepted, rejected or done';
    END IF;
    SELECT * INTO x FROM extractions WHERE id = p_extraction FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'extraction % not found', p_extraction;
    END IF;
    IF p_decision = 'done' AND x.status <> 'accepted' THEN
        RAISE EXCEPTION 'only accepted next steps can be marked done';
    END IF;
    IF p_decision IN ('accepted', 'rejected') AND x.status <> 'proposed' THEN
        RAISE EXCEPTION 'extraction % already decided (%)', p_extraction, x.status;
    END IF;

    UPDATE extractions SET status = p_decision, decided_by = p_user, decided_at = now() WHERE id = p_extraction;
    SELECT source_id INTO v_source FROM interactions WHERE id = x.interaction_id;

    IF p_decision = 'accepted' AND x.kind = 'intro' THEN
        v_introducer := person_by_email(x.payload #>> '{introducer,email}');
        FOR item IN SELECT * FROM jsonb_array_elements(x.payload -> 'introduced') LOOP
            v_person := person_by_email(item ->> 'email');
            IF v_person IS NOT NULL THEN
                v_people := v_people || v_person;
            END IF;
        END LOOP;
        FOREACH v_person IN ARRAY v_people LOOP
            IF v_introducer IS NOT NULL AND v_introducer <> v_person THEN
                INSERT INTO edges (tenant_id, src_id, dst_id, type, props, source_id, confidence)
                VALUES (x.tenant_id, v_introducer, v_person, 'introduced',
                        jsonb_build_object('extraction_id', x.id, 'strength', 0.6), v_source, x.confidence)
                ON CONFLICT (tenant_id, src_id, dst_id, type) WHERE valid_to IS NULL DO NOTHING;
            END IF;
            FOREACH v_other IN ARRAY v_people LOOP
                IF v_other > v_person THEN
                    INSERT INTO edges (tenant_id, src_id, dst_id, type, props, source_id, confidence)
                    VALUES (x.tenant_id, v_person, v_other, 'introduced',
                            jsonb_build_object('extraction_id', x.id, 'by', v_introducer, 'strength', 0.5),
                            v_source, x.confidence)
                    ON CONFLICT (tenant_id, src_id, dst_id, type) WHERE valid_to IS NULL DO NOTHING;
                END IF;
            END LOOP;
        END LOOP;
    ELSIF p_decision = 'accepted' AND x.kind = 'deal_mention' THEN
        v_domain := nullif(lower(regexp_replace(x.payload ->> 'company_domain', '^(https?://)?(www\.)?', '')), '');
        v_domain := split_part(v_domain, '/', 1);
        IF v_domain IS NOT NULL AND v_domain <> '' THEN
            SELECT coalesce(e.merged_into, e.id) INTO v_company
              FROM identifiers i JOIN entities e ON e.id = i.entity_id
             WHERE i.kind = 'domain' AND i.value = v_domain AND e.type = 'company';
        END IF;
        IF v_company IS NULL THEN
            SELECT c.id INTO v_company FROM companies c JOIN entities e ON e.id = c.id
             WHERE e.merged_into IS NULL AND lower(c.name) = lower(x.payload ->> 'company_name') LIMIT 1;
        END IF;
        IF v_company IS NULL THEN
            INSERT INTO entities (tenant_id, type, canonical_name)
            VALUES (x.tenant_id, 'company', x.payload ->> 'company_name') RETURNING id INTO v_company;
            INSERT INTO companies (id, tenant_id, name, domain, description)
            VALUES (v_company, x.tenant_id, x.payload ->> 'company_name', nullif(v_domain, ''),
                    nullif(x.payload ->> 'summary', ''));
            IF nullif(v_domain, '') IS NOT NULL THEN
                INSERT INTO identifiers (tenant_id, entity_id, kind, value, source_id)
                VALUES (x.tenant_id, v_company, 'domain', v_domain, v_source) ON CONFLICT DO NOTHING;
            END IF;
        END IF;
        SELECT d.id INTO v_deal FROM deals d JOIN entities e ON e.id = d.id
         WHERE d.company_id = v_company AND e.merged_into IS NULL AND d.stage NOT IN ('passed', 'closed')
         LIMIT 1;
        IF v_deal IS NULL THEN
            INSERT INTO entities (tenant_id, type, canonical_name)
            VALUES (x.tenant_id, 'deal', x.payload ->> 'company_name') RETURNING id INTO v_deal;
            INSERT INTO deals (id, tenant_id, company_id, name, stage, round_size_usd, created_by)
            VALUES (v_deal, x.tenant_id, v_company, x.payload ->> 'company_name', 'sourced',
                    nullif((x.payload ->> 'round_size_usd')::numeric, 0), p_user);
            INSERT INTO outbox (tenant_id, topic, key, payload)
            VALUES (x.tenant_id, 'deals.events', v_deal::text, jsonb_build_object(
                'type', 'deal.created', 'tenant_id', x.tenant_id, 'deal_id', v_deal, 'name', x.payload ->> 'company_name',
                'stage', 'sourced', 'actor_id', p_user, 'extraction_id', x.id));
        END IF;
        UPDATE interactions SET deal_id = coalesce(deal_id, v_deal) WHERE id = x.interaction_id;
    END IF;

    INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, details)
    VALUES (x.tenant_id, 'user', p_user, 'extraction.' || p_decision, 'extraction', p_extraction::text,
            jsonb_build_object('kind', x.kind, 'deal_id', v_deal));
    RETURN v_deal;
END $$;

-- 0002_entity_resolution: merging entities and deciding review-queue items.
-- Both functions run as the caller (SECURITY INVOKER), so row-level security
-- still confines them to the caller's tenant.

CREATE FUNCTION merge_entities(p_from uuid, p_into uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_type entity_type;
    e record;
BEGIN
    IF p_from = p_into THEN
        RETURN;
    END IF;

    SELECT type INTO v_type FROM entities WHERE id = p_from AND merged_into IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'entity % not found or already merged', p_from;
    END IF;
    PERFORM 1 FROM entities WHERE id = p_into AND type = v_type AND merged_into IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'merge target % not found, merged, or of a different type', p_into;
    END IF;

    UPDATE identifiers SET entity_id = p_into WHERE entity_id = p_from;

    IF v_type = 'person' THEN
        UPDATE interaction_participants SET person_id = p_into WHERE person_id = p_from;
        UPDATE users SET person_id = p_into WHERE person_id = p_from;
        -- Keep fields the surviving record is missing.
        UPDATE people t SET
            title         = coalesce(t.title, f.title),
            company_id    = coalesce(t.company_id, f.company_id),
            primary_email = coalesce(t.primary_email, f.primary_email),
            is_internal   = t.is_internal OR f.is_internal
        FROM people f WHERE t.id = p_into AND f.id = p_from;
    ELSIF v_type = 'company' THEN
        UPDATE people SET company_id = p_into WHERE company_id = p_from;
        UPDATE deals SET company_id = p_into WHERE company_id = p_from;
        UPDATE companies t SET
            domain      = coalesce(t.domain, f.domain),
            registry_id = coalesce(t.registry_id, f.registry_id),
            country     = coalesce(t.country, f.country),
            description = coalesce(t.description, f.description),
            website     = coalesce(t.website, f.website)
        FROM companies f WHERE t.id = p_into AND f.id = p_from;
    END IF;

    -- Re-point live edges. If the surviving entity already has the same edge,
    -- close the duplicate instead; self-loops created by the merge are closed.
    FOR e IN SELECT * FROM edges WHERE (src_id = p_from OR dst_id = p_from) AND valid_to IS NULL LOOP
        DECLARE
            v_src uuid := CASE WHEN e.src_id = p_from THEN p_into ELSE e.src_id END;
            v_dst uuid := CASE WHEN e.dst_id = p_from THEN p_into ELSE e.dst_id END;
        BEGIN
            IF v_src = v_dst OR EXISTS (
                SELECT 1 FROM edges x
                WHERE x.tenant_id = e.tenant_id AND x.src_id = v_src AND x.dst_id = v_dst
                  AND x.type = e.type AND x.valid_to IS NULL AND x.id <> e.id
            ) THEN
                UPDATE edges SET valid_to = now(), updated_at = now() WHERE id = e.id;
            ELSE
                UPDATE edges SET src_id = v_src, dst_id = v_dst, updated_at = now() WHERE id = e.id;
            END IF;
        END;
    END LOOP;

    UPDATE er_candidates SET candidate_entity_id = p_into
        WHERE candidate_entity_id = p_from AND status = 'pending' AND provisional_entity_id <> p_into;
    UPDATE er_candidates SET status = 'distinct', decided_at = now(),
        features = features || '{"superseded_by_merge": true}'
        WHERE status = 'pending' AND (provisional_entity_id = p_from OR candidate_entity_id = p_from);

    UPDATE entities SET merged_into = p_into, updated_at = now() WHERE id = p_from;
    UPDATE entities SET updated_at = now() WHERE id = p_into;
END $$;

-- Resolve one review-queue item. 'merged' folds the provisional entity into
-- the candidate; 'distinct' keeps them apart.
CREATE FUNCTION er_decide(p_candidate uuid, p_decision text, p_user uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    c er_candidates;
BEGIN
    IF p_decision NOT IN ('merged', 'distinct') THEN
        RAISE EXCEPTION 'decision must be merged or distinct';
    END IF;
    SELECT * INTO c FROM er_candidates WHERE id = p_candidate FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'candidate % not found', p_candidate;
    END IF;
    IF c.status <> 'pending' THEN
        RAISE EXCEPTION 'candidate % already decided (%)', p_candidate, c.status;
    END IF;

    UPDATE er_candidates SET status = p_decision, decided_by = p_user, decided_at = now()
        WHERE id = p_candidate;

    IF p_decision = 'merged' THEN
        PERFORM merge_entities(c.provisional_entity_id, c.candidate_entity_id);
    END IF;

    INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, details)
    VALUES (c.tenant_id, 'user', p_user, 'er.' || p_decision, 'er_candidate', p_candidate::text,
            jsonb_build_object('provisional', c.provisional_entity_id, 'candidate', c.candidate_entity_id, 'score', c.score));
END $$;

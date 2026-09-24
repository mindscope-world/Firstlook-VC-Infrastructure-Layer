-- 0006_tenant_purge: allow removing a whole tenant (offboarding, erasure)
-- without weakening the audit log's append-only guarantee day to day.
--
-- Updates are always rejected. Deletes are rejected unless the transaction
-- has set firstlook.audit_purge = 'on', which only purge_tenant() does. The
-- app role still has no DELETE privilege on audit_events at all.

CREATE OR REPLACE FUNCTION audit_events_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_setting('firstlook.audit_purge', true) = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'audit_events is append-only';
END $$;

-- Deletes a tenant and everything it owns. Runs as the function owner so the
-- cascade reaches audit rows; callable only by the system role.
CREATE FUNCTION purge_tenant(p_tenant uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    PERFORM set_config('firstlook.audit_purge', 'on', true);
    DELETE FROM tenants WHERE id = p_tenant;
    PERFORM set_config('firstlook.audit_purge', 'off', true);
END $$;

REVOKE EXECUTE ON FUNCTION purge_tenant(uuid) FROM PUBLIC, firstlook_app;
GRANT EXECUTE ON FUNCTION purge_tenant(uuid) TO firstlook_system;

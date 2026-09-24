-- Runs once when the Postgres volume is first created.
-- firstlook        : owner, runs migrations (superuser in local dev only)
-- firstlook_app    : what services connect as; subject to row-level security
-- firstlook_system : cross-tenant jobs (scheduler, outbox relay); BYPASSRLS
CREATE ROLE firstlook_app LOGIN PASSWORD 'firstlook_app' NOBYPASSRLS;
CREATE ROLE firstlook_system LOGIN PASSWORD 'firstlook_system' BYPASSRLS;
GRANT CONNECT ON DATABASE firstlook TO firstlook_app, firstlook_system;
CREATE DATABASE langfuse OWNER firstlook;
CREATE DATABASE firstlook_test OWNER firstlook;

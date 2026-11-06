-- Read-only access for business analytics, which connects to the
-- replicas via Teleport. Run by hand on the primary, as the postgres
-- user, after any change to this file; the role and its privileges
-- reach the replicas via replication.
--
-- This is meant to be authoritative and is written to be safe to re-run.
-- Any changes to the granted privileges for analytics_reader should be
-- checked into this file.

BEGIN;

DO $$BEGIN
    CREATE ROLE analytics_reader LOGIN;
EXCEPTION WHEN duplicate_object THEN
    RAISE NOTICE 'role already exists';
END$$;
ALTER ROLE analytics_reader RESET ALL;
ALTER ROLE analytics_reader CONNECTION LIMIT 3;
ALTER ROLE analytics_reader SET search_path = zulip;

GRANT CONNECT ON DATABASE zulip TO analytics_reader;
GRANT USAGE ON SCHEMA zulip TO analytics_reader;

SET LOCAL search_path = zulip;

REVOKE ALL ON ALL TABLES IN SCHEMA zulip FROM analytics_reader;

GRANT SELECT ON
    analytics_fillstate,
    analytics_installationcount,
    analytics_realmcount,
    analytics_streamcount,
    analytics_usercount
TO analytics_reader;

GRANT SELECT (id, string_id, date_created, deactivated, plan_type)
    ON zerver_realm TO analytics_reader;

GRANT SELECT (id, realm_id, date_joined, is_active, is_bot)
    ON zerver_userprofile TO analytics_reader;

GRANT SELECT (id, realm_id, date_sent)
    ON zerver_message TO analytics_reader;

COMMIT;

-- Read-only access for business analytics, which connects to the
-- replicas via Teleport. Run by hand on the primary, as the postgres
-- user, after any change to this file; the role and its privileges
-- reach the replicas via replication.
--
-- This is meant to be authoritative and is written to be safe to re-run.
-- Any changes to the granted privileges for analytics_reader should be
-- checked into this file.

BEGIN;
-- Recreating the views waits for queries which are reading them; give
-- up rather than hold up other queries behind us. Just re-run it.
SET LOCAL lock_timeout = '3s';

DO $$BEGIN
    CREATE ROLE analytics_reader LOGIN;
EXCEPTION WHEN duplicate_object THEN
    RAISE NOTICE 'role already exists';
END$$;
ALTER ROLE analytics_reader RESET ALL;
ALTER ROLE analytics_reader CONNECTION LIMIT 3;
-- The views in analytics_reader_views take the place of the tables of
-- the same name. Since that schema comes first in the search path, a
-- SELECT from zerver_realmauditlog by analytics_reader reads the view
-- analytics_reader_views.zerver_realmauditlog. Queries can thus use
-- the usual table names, without caring which tables are views.
ALTER ROLE analytics_reader SET search_path = analytics_reader_views, zulip;

GRANT CONNECT ON DATABASE zulip TO analytics_reader;
GRANT USAGE ON SCHEMA zulip TO analytics_reader;

SET LOCAL search_path = zulip;

REVOKE ALL ON ALL TABLES IN SCHEMA zulip FROM analytics_reader;

GRANT SELECT ON
    analytics_fillstate,
    analytics_installationcount,
    analytics_realmcount,
    django_content_type
TO analytics_reader;

GRANT SELECT (id, realm_id, type, content_type_id, object_id, date_sent)
    ON confirmation_confirmation TO analytics_reader;
GRANT SELECT (id, realm_id, remote_realm_id, remote_server_id)
    ON corporate_customer TO analytics_reader;
GRANT SELECT (
    id, customer_id, tier, status, billing_schedule,
    billing_cycle_anchor, fixed_price, price_per_license
) ON corporate_customerplan TO analytics_reader;
GRANT SELECT (id, plan_id, event_time, licenses_at_next_renewal)
    ON corporate_licenseledger TO analytics_reader;
GRANT SELECT (
    id, string_id, date_created, deactivated,
    demo_organization_scheduled_deletion_date, org_type, plan_type
) ON zerver_realm TO analytics_reader;
GRANT SELECT (realm_id, is_active, is_bot, bot_type, is_mirror_dummy)
    ON zerver_userprofile TO analytics_reader;
GRANT SELECT (server_id, remote_id, end_time)
    ON zilencer_remoteinstallationcount TO analytics_reader;
GRANT SELECT (
    id, server_id, plan_type, is_system_bot_realm,
    realm_deactivated, realm_locally_deleted, registration_deactivated
) ON zilencer_remoterealm TO analytics_reader;
GRANT SELECT (
    id, server_id, remote_realm_id, remote_id,
    property, subgroup, end_time, value
) ON zilencer_remoterealmcount TO analytics_reader;
GRANT SELECT (id, deactivated, plan_type)
    ON zilencer_remotezulipserver TO analytics_reader;
GRANT SELECT (server_id, event_type, event_time, backfilled)
    ON zilencer_remotezulipserverauditlog TO analytics_reader;

-- Key for hashing values which analytics only compares for equality.
-- Unlike view and function definitions, which every role can read via
-- the system catalogs, this table is readable only by its owner. It
-- is created once and never replaced, since replacing it would change
-- every hash.
CREATE SCHEMA IF NOT EXISTS analytics_reader_secret;
CREATE TABLE IF NOT EXISTS analytics_reader_secret.hash_key (key bytea NOT NULL);
INSERT INTO analytics_reader_secret.hash_key
    SELECT sha256(convert_to(gen_random_uuid()::text, 'UTF8'))
    WHERE NOT EXISTS (SELECT 1 FROM analytics_reader_secret.hash_key);

-- Views for data which needs hashing or filtering. They read the
-- tables with their owner's privileges, so analytics_reader needs no
-- access to the tables themselves. security_barrier ensures the view's
-- filters are applied before any conditions in the reader's query.
--
-- PostgreSQL does not allow changing the type of a column which a view
-- reads. If a migration fails for that reason, run
-- "DROP SCHEMA analytics_reader_views CASCADE;", retry the migration,
-- and then re-run this file.
DROP SCHEMA IF EXISTS analytics_reader_views CASCADE;
CREATE SCHEMA analytics_reader_views;

CREATE VIEW analytics_reader_views.zerver_preregistrationrealm WITH (security_barrier) AS
SELECT
    id,
    created_realm_id,
    string_id,
    encode(sha256(
        (SELECT key FROM analytics_reader_secret.hash_key) || convert_to(lower(email), 'UTF8')
    ), 'hex') AS email
FROM zulip.zerver_preregistrationrealm;

-- extra_data keeps only the required keys for each event type.
CREATE VIEW analytics_reader_views.zerver_realmauditlog WITH (security_barrier) AS
SELECT
    log.id,
    log.realm_id,
    log.event_type,
    log.event_time,
    (
        SELECT coalesce(jsonb_object_agg(item.key, item.value), '{}')
        FROM jsonb_each(log.extra_data) AS item
        WHERE item.key = ANY (CASE log.event_type
            -- REALM_DEACTIVATED
            WHEN 201 THEN ARRAY['deactivation_reason']
            -- REALM_SUBDOMAIN_CHANGED; not the old and new subdomains
            WHEN 214 THEN ARRAY['was_demo_organization']
            -- REALM_CREATED
            WHEN 215 THEN ARRAY[
                'how_realm_creator_found_zulip',
                'how_realm_creator_found_zulip_extra_context'
            ]
            -- REALM_ORG_TYPE_CHANGED
            WHEN 217 THEN ARRAY['1', 'old_value']
            -- CUSTOMER_PLAN_CREATED
            WHEN 502 THEN ARRAY['billing_cycle_anchor', 'customer_id', 'status']
            ELSE ARRAY[]::text[]
        END)
    ) AS extra_data
FROM zulip.zerver_realmauditlog AS log
WHERE log.event_type IN (201, 202, 210, 214, 215, 217, 502);

-- extra_data keeps only the user counts by role.
CREATE VIEW analytics_reader_views.zilencer_remoterealmauditlog WITH (security_barrier) AS
SELECT
    id,
    remote_realm_id,
    event_type,
    event_time,
    CASE WHEN extra_data ? '10' THEN jsonb_build_object('10', extra_data -> '10')
         ELSE '{}' END AS extra_data
FROM zulip.zilencer_remoterealmauditlog
WHERE event_type IN (101, 102, 103, 104, 105, 201, 202, 229, 725);

GRANT USAGE ON SCHEMA analytics_reader_views TO analytics_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics_reader_views TO analytics_reader;

COMMIT;

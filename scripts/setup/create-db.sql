\connect postgres
DROP DATABASE IF EXISTS zulip;
DO $$BEGIN
    CREATE USER zulip;
EXCEPTION WHEN duplicate_object THEN
    RAISE NOTICE 'zulip user already exists';
END$$;
ALTER ROLE zulip SET search_path TO zulip,public;
CREATE DATABASE zulip OWNER=zulip;
\connect zulip
CREATE SCHEMA zulip AUTHORIZATION zulip;

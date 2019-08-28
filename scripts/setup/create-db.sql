CREATE USER zulip;
ALTER ROLE zulip SET search_path TO zulip,public;
CREATE DATABASE zulip OWNER=zulip;
\connect zulip
CREATE SCHEMA zulip AUTHORIZATION zulip;

\set dbuser :dbuser
SELECT CASE WHEN :'dbuser' = ':dbuser' THEN 'zulip' ELSE :'dbuser' END AS dbuser \gset
\set dbname :dbname
SELECT CASE WHEN :'dbname' = ':dbname' THEN 'zulip' ELSE :'dbname' END AS dbname \gset

\connect postgres
DROP DATABASE IF EXISTS :"dbname";
SELECT format($$BEGIN
    CREATE USER %I;
EXCEPTION WHEN duplicate_object THEN
    RAISE NOTICE 'user already exists';
END$$, :'dbuser') AS code \gset
DO :'code';
ALTER ROLE :"dbuser" SET search_path TO :"dbname",public;
CREATE DATABASE :"dbname"
    OWNER=:dbuser
    ENCODING=UTF8
    LC_COLLATE='C.UTF-8'
    LC_CTYPE='C.UTF-8'
    TEMPLATE=template0;
\connect :"dbname"
CREATE SCHEMA zulip AUTHORIZATION :"dbuser";

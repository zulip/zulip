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

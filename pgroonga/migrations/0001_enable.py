from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0001_initial'),
    ]

    database_setting = settings.DATABASES["default"]
    if "postgres" in database_setting["ENGINE"]:
        operations = [
            migrations.RunSQL([("""
DO $$BEGIN
EXECUTE format('ALTER ROLE %%I SET search_path TO %%L,public,pgroonga,pg_catalog', %(USER)s, %(SCHEMA)s);

SET search_path = %(SCHEMA)s,public,pgroonga,pg_catalog;

ALTER TABLE zerver_message ADD COLUMN search_pgroonga text;

-- TODO: We want to use CREATE INDEX CONCURRENTLY but it can't be used in
-- transaction. Django uses transaction implicitly.
-- Django 1.10 may solve the problem.
CREATE INDEX zerver_message_search_pgroonga ON zerver_message
  USING pgroonga(search_pgroonga pgroonga.text_full_text_search_ops);
END$$
""", database_setting)],
                              [("""
DO $$BEGIN
SET search_path = %(SCHEMA)s,public,pgroonga,pg_catalog;

DROP INDEX zerver_message_search_pgroonga;
ALTER TABLE zerver_message DROP COLUMN search_pgroonga;

SET search_path = %(SCHEMA)s,public;

EXECUTE format('ALTER ROLE %%I SET search_path TO %%L,public', %(USER)s, %(SCHEMA)s);
END$$
""", database_setting)]),
        ]
    else:
        operations = []

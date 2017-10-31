# -*- coding: utf-8 -*-
from django.db import models, migrations
from django.contrib.postgres import operations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0001_initial'),
    ]

    database_setting = settings.DATABASES["default"]
    if "postgres" in database_setting["ENGINE"]:
        operations = [
            migrations.RunSQL("""
ALTER ROLE %(USER)s SET search_path TO %(SCHEMA)s,public,pgroonga,pg_catalog;

SET search_path = %(SCHEMA)s,public,pgroonga,pg_catalog;

ALTER TABLE zerver_message ADD COLUMN search_pgroonga text;

UPDATE zerver_message SET search_pgroonga = subject || ' ' || rendered_content;

-- TODO: We want to use CREATE INDEX CONCURRENTLY but it can't be used in
-- transaction. Django uses transaction implicitly.
-- Django 1.10 may solve the problem.
CREATE INDEX zerver_message_search_pgroonga ON zerver_message
  USING pgroonga(search_pgroonga pgroonga.text_full_text_search_ops);
""" % database_setting,
                              """
SET search_path = %(SCHEMA)s,public,pgroonga,pg_catalog;

DROP INDEX zerver_message_search_pgroonga;
ALTER TABLE zerver_message DROP COLUMN search_pgroonga;

SET search_path = %(SCHEMA)s,public;

ALTER ROLE %(USER)s SET search_path TO %(SCHEMA)s,public;
""" % database_setting),
        ]
    else:
        operations = []

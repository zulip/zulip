# -*- coding: utf-8 -*-
from django.db import migrations
from django.conf import settings


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('pgroonga', '0002_html_escape_subject'),
    ]

    database_setting = settings.DATABASES["default"]
    operations = [
        migrations.RunSQL(["""
ALTER ROLE %(USER)s SET search_path TO %(SCHEMA)s,public;

SET search_path = %(SCHEMA)s,public;

DROP INDEX zerver_message_search_pgroonga;
""" % database_setting, """

CREATE INDEX CONCURRENTLY zerver_message_search_pgroonga ON zerver_message
  USING pgroonga(search_pgroonga pgroonga_text_full_text_search_ops_v2);
"""],
                          ["""
ALTER ROLE %(USER)s SET search_path TO %(SCHEMA)s,public,pgroonga,pg_catalog;

SET search_path = %(SCHEMA)s,public,pgroonga,pg_catalog;

DROP INDEX zerver_message_search_pgroonga;
""" % database_setting, """

CREATE INDEX CONCURRENTLY zerver_message_search_pgroonga ON zerver_message
  USING pgroonga(search_pgroonga pgroonga.text_full_text_search_ops);
        """])
    ]

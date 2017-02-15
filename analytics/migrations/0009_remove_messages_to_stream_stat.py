# -*- coding: utf-8 -*-
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db import migrations

from analytics.lib.counts import do_delete_count_stat

def delete_messages_sent_to_stream_stat(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    do_delete_count_stat('messages_sent_to_stream:is_bot')

class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0008_add_count_indexes'),
    ]

    operations = [
        migrations.RunPython(delete_messages_sent_to_stream_stat),
    ]

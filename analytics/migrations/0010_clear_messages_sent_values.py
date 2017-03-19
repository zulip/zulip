# -*- coding: utf-8 -*-
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db import migrations

from analytics.lib.counts import do_delete_count_stat


def clear_message_sent_by_message_type_values(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    do_delete_count_stat('messages_sent:message_type:day')


class Migration(migrations.Migration):

    dependencies = [('analytics', '0009_remove_messages_to_stream_stat')]

    operations = [
        migrations.RunPython(clear_message_sent_by_message_type_values),
    ]

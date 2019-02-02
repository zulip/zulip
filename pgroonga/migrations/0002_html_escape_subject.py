# -*- coding: utf-8 -*-
from django.db import migrations, connection
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from zerver.lib.migrate import do_batch_update

def rebuild_pgroonga_index(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    with connection.cursor() as cursor:
        do_batch_update(cursor, 'zerver_message', ['search_pgroonga'],
                        ["escape_html(subject) || ' ' || rendered_content"],
                        escape=False, batch_size=10000)

class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('pgroonga', '0001_enable'),
    ]

    operations = [
        migrations.RunPython(rebuild_pgroonga_index,
                             reverse_code=migrations.RunPython.noop)
    ]

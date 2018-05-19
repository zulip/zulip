# -*- coding: utf-8 -*-
from django.db import models, migrations, connection
from django.contrib.postgres import operations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

def rebuild_pgroonga_index(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    BATCH_SIZE = 10000

    Message = apps.get_model("zerver", "Message")
    message_ids = Message.objects.values_list('id', flat=True)
    with connection.cursor() as cursor:
        for i in range(0, len(message_ids), BATCH_SIZE):
            batch_ids = ', '.join(str(id) for id in message_ids[i:i+BATCH_SIZE])
            cursor.execute("UPDATE zerver_message SET "
                           "search_pgroonga = "
                           "escape_html(subject) || ' ' || rendered_content "
                           "WHERE id IN (%s)" % (batch_ids,))

class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('pgroonga', '0001_enable'),
    ]

    operations = [
        migrations.RunPython(rebuild_pgroonga_index,
                             reverse_code=migrations.RunPython.noop)
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from zerver.lib.migrate import (
    create_topics_for_message_range,
    migrate_all_messages,
)
from zerver.models import (
    Message,
)

# These are to to help type-check the target of RunPython (backfill_topics).
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

def backfill_topics(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    if Message.objects.all().count():
        migrate_all_messages(
            range_method=create_topics_for_message_range,
            batch_size=10000,
            max_num_batches=99999,
            verbose=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0026_add_topic_table'),
    ]

    operations = [
        migrations.RunPython(backfill_topics),
    ]

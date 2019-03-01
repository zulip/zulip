# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

from django.db.migrations.state import StateApps
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor

from zerver.lib.bugdown import convert as bugdown_convert

def render_all_stream_descriptions(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    Stream = apps.get_model('zerver', 'Stream')
    all_streams = Stream.objects.exclude(description='')
    for stream in all_streams:
        stream.rendered_description = bugdown_convert(stream.description,
                                                      no_previews=True)
        stream.save(update_fields=["rendered_description"])


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0205_remove_realmauditlog_requires_billing_update'),
    ]

    operations = [
        migrations.AddField(
            model_name='stream',
            name='rendered_description',
            field=models.TextField(default=''),
        ),
        migrations.RunPython(render_all_stream_descriptions,
                             reverse_code=migrations.RunPython.noop),
    ]

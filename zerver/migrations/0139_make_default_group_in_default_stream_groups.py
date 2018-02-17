# -*- coding: utf-8 -*-

from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

def add_existing_default_streams_to_default_group(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    DefaultStreamGroup = apps.get_model('zerver', 'DefaultStreamGroup')
    DefaultStream = apps.get_model('zerver', 'DefaultStream')
    Realm = apps.get_model('zerver', 'Realm')

    for realm in Realm.objects.all():
        if not DefaultStreamGroup.objects.filter(realm=realm, name="default").exists():
            default_stream_objects = DefaultStream.objects.filter(realm=realm)
            default_streams = [default_stream_object.stream for default_stream_object in default_stream_objects]
            group = DefaultStreamGroup.objects.create(realm=realm,  name="default")
            group.streams = default_streams
            group.save()

class Migration(migrations.Migration):

    dependencies = [
         ('zerver', '0137_realm_upload_quota_gb'),
    ]

    operations = [
        migrations.RunPython(add_existing_default_streams_to_default_group)
]
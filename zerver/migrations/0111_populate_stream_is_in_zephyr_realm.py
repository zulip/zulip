# -*- coding: utf-8 -*-

from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db import connection, migrations

def populate_is_zephyr(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    Realm = apps.get_model("zerver", "Realm")
    Stream = apps.get_model("zerver", "Stream")

    realms = Realm.objects.filter(
        string_id='zephyr',
    )

    for realm in realms:
        Stream.objects.filter(
            realm_id=realm.id
        ).update(
            is_in_zephyr_realm=True
        )

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0110_stream_is_in_zephyr_realm'),
    ]

    operations = [
        migrations.RunPython(populate_is_zephyr),
    ]

# Generated by Django 2.2.14 on 2020-08-10 20:21

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def remove_default_status_of_default_private_streams(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    DefaultStream = apps.get_model("zerver", "DefaultStream")
    DefaultStream.objects.filter(stream__invite_only=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0303_realm_wildcard_mention_policy"),
    ]

    operations = [
        migrations.RunPython(
            remove_default_status_of_default_private_streams,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]

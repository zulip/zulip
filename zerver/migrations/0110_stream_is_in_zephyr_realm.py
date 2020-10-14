# Generated by Django 1.11.5 on 2017-10-08 18:37
from django.db import migrations, models
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps


def populate_is_zephyr(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    Realm = apps.get_model("zerver", "Realm")
    Stream = apps.get_model("zerver", "Stream")

    realms = Realm.objects.filter(
        string_id='zephyr',
    )

    for realm in realms:
        Stream.objects.filter(
            realm_id=realm.id
        ).update(
            is_in_zephyr_realm=True,
        )

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0109_mark_tutorial_status_finished'),
    ]

    operations = [
        migrations.AddField(
            model_name='stream',
            name='is_in_zephyr_realm',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(populate_is_zephyr,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]

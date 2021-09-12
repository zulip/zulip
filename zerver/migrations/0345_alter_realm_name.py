# Generated by Django 3.2.6 on 2021-09-08 22:35

from django.conf import settings
from django.db import migrations, models
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps


def rename_system_bot_realm(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    # Prior to this migration, the system bot realm had name incorrectly set to null.
    Realm = apps.get_model("zerver", "Realm")
    Realm.objects.filter(name=None, string_id=settings.SYSTEM_BOT_REALM).update(
        name="System bot realm"
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0344_alter_emojiset_default_value"),
    ]

    operations = [
        migrations.RunPython(
            rename_system_bot_realm,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
        migrations.AlterField(
            model_name="realm",
            name="name",
            field=models.CharField(max_length=40),
        ),
    ]

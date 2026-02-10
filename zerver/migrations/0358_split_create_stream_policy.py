from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import F


def copy_stream_policy_field(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Realm = apps.get_model("zerver", "Realm")
    Realm.objects.all().update(create_public_stream_policy=F("create_stream_policy"))
    Realm.objects.all().update(create_private_stream_policy=F("create_stream_policy"))


# When reversing the migration, we have to pick one of the new fields
# to store in the original field name. This does destroy information,
# but in most cases downgrades that would reverse migrations happen
# before any real usage, so it's very likely that both values are
# identical.
def reverse_code(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Realm = apps.get_model("zerver", "Realm")
    Realm.objects.all().update(create_stream_policy=F("create_public_stream_policy"))


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0357_remove_realm_allow_message_deleting"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="create_private_stream_policy",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="realm",
            name="create_public_stream_policy",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.RunPython(copy_stream_policy_field, reverse_code=reverse_code, elidable=True),
        migrations.RemoveField(
            model_name="realm",
            name="create_stream_policy",
        ),
    ]

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def set_default_value_for_stream_topic_access_group(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Stream = apps.get_model("zerver", "Stream")
    Realm = apps.get_model("zerver", "Realm")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")

    for realm in Realm.objects.all():
        everyone_group = NamedUserGroup.objects.get(
            name="role:everyone", realm=realm, is_system_group=True
        )
        Stream.objects.filter(realm=realm, stream_topic_access_group=None).update(
            stream_topic_access_group=everyone_group
        )


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0537_stream_stream_topic_access_group"),
    ]

    operations = [
        migrations.RunPython(
            set_default_value_for_stream_topic_access_group,
            elidable=True,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

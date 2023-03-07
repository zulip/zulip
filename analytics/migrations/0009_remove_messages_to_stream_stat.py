from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def delete_messages_sent_to_stream_stat(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    UserCount = apps.get_model("analytics", "UserCount")
    StreamCount = apps.get_model("analytics", "StreamCount")
    RealmCount = apps.get_model("analytics", "RealmCount")
    InstallationCount = apps.get_model("analytics", "InstallationCount")
    FillState = apps.get_model("analytics", "FillState")

    property = "messages_sent_to_stream:is_bot"
    UserCount.objects.filter(property=property).delete()
    StreamCount.objects.filter(property=property).delete()
    RealmCount.objects.filter(property=property).delete()
    InstallationCount.objects.filter(property=property).delete()
    FillState.objects.filter(property=property).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0008_add_count_indexes"),
    ]

    operations = [
        migrations.RunPython(delete_messages_sent_to_stream_stat),
    ]

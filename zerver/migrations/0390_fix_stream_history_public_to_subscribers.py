from django.db import migrations
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps


def fix_stream_history_public_to_subscribers(
    apps: StateApps, schema_editor: DatabaseSchemaEditor
) -> None:
    Stream = apps.get_model("zerver", "Stream")
    Stream.objects.filter(
        invite_only=False, is_in_zephyr_realm=False, history_public_to_subscribers=False
    ).update(history_public_to_subscribers=True)


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0389_userprofile_display_emoji_reaction_users"),
    ]

    operations = [
        migrations.RunPython(fix_stream_history_public_to_subscribers, elidable=True),
    ]

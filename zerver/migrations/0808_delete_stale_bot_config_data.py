from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

# Copied from zerver/models/users.py.
INCOMING_WEBHOOK_BOT = 2
EMBEDDED_BOT = 4


def delete_stale_bot_config_data(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    # Before the fix, PATCH /bots/{bot_id} accepted config_data for any bot
    # type and wrote rows into BotConfigData. Only INCOMING_WEBHOOK_BOT and
    # EMBEDDED_BOT have config_data, so any rows attached to other bot types
    # are dead weight.
    BotConfigData = apps.get_model("zerver", "BotConfigData")
    BotConfigData.objects.exclude(
        bot_profile__bot_type__in=[INCOMING_WEBHOOK_BOT, EMBEDDED_BOT],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0807_usertopic_zerver_usertopic_user_visibility_recipient_idx"),
    ]

    operations = [
        migrations.RunPython(
            delete_stale_bot_config_data,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]

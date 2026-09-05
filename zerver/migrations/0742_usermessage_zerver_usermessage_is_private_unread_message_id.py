from django.conf import settings
from django.db import migrations, models

from zerver.lib.migrate import add_index


class Migration(migrations.Migration):
    atomic = not settings.MIGRATIONS_ADD_REMOVE_INDEXES_CONCURRENTLY

    dependencies = [
        ("zerver", "0741_pushdevice_zerver_pushdevice_user_bouncer_device_id_idx"),
    ]

    operations = [
        add_index(
            model_name="usermessage",
            index=models.Index(
                models.F("user_profile"),
                models.F("message"),
                condition=models.Q(("flags__andnz", 2048), ("flags__andz", 1)),
                name="zerver_usermessage_is_private_unread_message_id",
            ),
        ),
        migrations.RunSQL("ANALYZE zerver_usermessage"),
    ]

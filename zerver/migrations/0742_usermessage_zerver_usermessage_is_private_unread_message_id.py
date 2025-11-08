from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("zerver", "0741_pushdevice_zerver_pushdevice_user_bouncer_device_id_idx"),
    ]

    operations = [
        AddIndexConcurrently(
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

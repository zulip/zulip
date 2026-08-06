from django.conf import settings
from django.db import migrations, models
from django.db.models import Q

from zerver.lib.migrate import add_index


class Migration(migrations.Migration):
    atomic = not settings.MIGRATIONS_ADD_REMOVE_INDEXES_CONCURRENTLY
    dependencies = [
        ("zerver", "0097_reactions_emoji_code"),
    ]

    operations = [
        add_index(
            model_name="usermessage",
            index=models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=512),
                name="zerver_usermessage_has_alert_word_message_id",
            ),
        ),
    ]

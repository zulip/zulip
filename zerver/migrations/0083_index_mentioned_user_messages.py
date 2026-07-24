from django.conf import settings
from django.db import migrations, models
from django.db.models import Q

from zerver.lib.migrate import add_index


class Migration(migrations.Migration):
    atomic = not settings.MIGRATIONS_ADD_REMOVE_INDEXES_CONCURRENTLY
    dependencies = [
        ("zerver", "0082_index_starred_user_messages"),
    ]

    operations = [
        add_index(
            model_name="usermessage",
            index=models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=8),
                name="zerver_usermessage_mentioned_message_id",
            ),
        ),
    ]

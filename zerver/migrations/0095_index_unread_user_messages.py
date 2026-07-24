from django.conf import settings
from django.db import migrations, models
from django.db.models import Q

from zerver.lib.migrate import add_index


class Migration(migrations.Migration):
    atomic = not settings.MIGRATIONS_ADD_REMOVE_INDEXES_CONCURRENTLY
    dependencies = [
        ("zerver", "0094_realm_filter_url_validator"),
    ]

    operations = [
        add_index(
            model_name="usermessage",
            index=models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andz=1),
                name="zerver_usermessage_unread_message_id",
            ),
        ),
    ]

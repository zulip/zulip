from django.conf import settings
from django.db import migrations, models

from zerver.lib.migrate import add_index


class Migration(migrations.Migration):
    atomic = not settings.MIGRATIONS_ADD_REMOVE_INDEXES_CONCURRENTLY

    dependencies = [
        ("zerver", "0818_usersetting_web_right_click_opens_message_actions_menu"),
    ]

    operations = [
        add_index(
            model_name="userpresence",
            index=models.Index(
                fields=["last_active_time", "user_profile"],
                name="zerver_userpresence_last_active_time_user_profile_id_idx",
            ),
        ),
    ]

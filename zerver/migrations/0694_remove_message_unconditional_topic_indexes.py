from django.conf import settings
from django.db import migrations

from zerver.lib.migrate import remove_index


class Migration(migrations.Migration):
    atomic = not settings.MIGRATIONS_ADD_REMOVE_INDEXES_CONCURRENTLY

    dependencies = [
        ("zerver", "0693_add_conditional_indexes_for_topic"),
    ]

    operations = [
        remove_index(
            model_name="message",
            name="zerver_message_realm_upper_subject_all",
        ),
        remove_index(
            model_name="message",
            name="zerver_message_realm_recipient_upper_subject_all",
        ),
        remove_index(
            model_name="message",
            name="zerver_message_realm_recipient_subject_all",
        ),
    ]

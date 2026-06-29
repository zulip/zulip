from django.db import migrations
from django.conf import settings
from zerver.utils import remove_index

class Migration(migrations.Migration):
    atomic = settings.ATOMIC_PG_MIGRATIONS

    dependencies = [
        ("zerver", "0472_add_message_realm_id_indexes"),
    ]

    operations = [
        remove_index(
            model_name="message",
            name="upper_subject_idx",
        ),
        remove_index(
            model_name="message",
            name="zerver_message_recipient_upper_subject",
        ),
        remove_index(
            model_name="message",
            name="zerver_message_recipient_subject",
        ),
        remove_index(
            model_name="scheduledmessage",
            name="zerver_unsent_scheduled_messages_by_user",
        ),
    ]

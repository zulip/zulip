from django.contrib.postgres.operations import RemoveIndexConcurrently
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0472_add_message_realm_id_indexes"),
    ]

    operations = [
        RemoveIndexConcurrently(
            model_name="message",
            name="upper_subject_idx",
        ),
        RemoveIndexConcurrently(
            model_name="message",
            name="zerver_message_recipient_upper_subject",
        ),
        RemoveIndexConcurrently(
            model_name="message",
            name="zerver_message_recipient_subject",
        ),
        RemoveIndexConcurrently(
            model_name="scheduledmessage",
            name="zerver_unsent_scheduled_messages_by_user",
        ),
    ]

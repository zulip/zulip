from django.contrib.postgres.operations import RemoveIndexConcurrently
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0693_add_conditional_indexes_for_topic"),
    ]

    operations = [
        RemoveIndexConcurrently(
            model_name="message",
            name="zerver_message_realm_upper_subject_all",
        ),
        RemoveIndexConcurrently(
            model_name="message",
            name="zerver_message_realm_recipient_upper_subject_all",
        ),
        RemoveIndexConcurrently(
            model_name="message",
            name="zerver_message_realm_recipient_subject_all",
        ),
    ]

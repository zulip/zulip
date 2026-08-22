from django.contrib.postgres.operations import RemoveIndexConcurrently
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0808_message_topic_indexes_nulls_first"),
    ]

    operations = [
        RemoveIndexConcurrently(
            model_name="message",
            name="zerver_message_realm_upper_subject_nulls_last",
        ),
        RemoveIndexConcurrently(
            model_name="message",
            name="zerver_message_realm_recipient_upper_subject_nulls_last",
        ),
        RemoveIndexConcurrently(
            model_name="message",
            name="zerver_message_realm_recipient_subject_nulls_last",
        ),
        RemoveIndexConcurrently(
            model_name="message",
            name="zerver_message_realm_id_nulls_last",
        ),
    ]

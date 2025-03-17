import django.db.models.functions.text
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0692_alter_message_is_channel_message"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="message",
            new_name="zerver_message_realm_upper_subject_all",
            old_name="zerver_message_realm_upper_subject",
        ),
        migrations.RenameIndex(
            model_name="message",
            new_name="zerver_message_realm_recipient_upper_subject_all",
            old_name="zerver_message_realm_recipient_upper_subject",
        ),
        migrations.RenameIndex(
            model_name="message",
            new_name="zerver_message_realm_recipient_subject_all",
            old_name="zerver_message_realm_recipient_subject",
        ),
        AddIndexConcurrently(
            model_name="message",
            index=models.Index(
                models.F("realm_id"),
                django.db.models.functions.text.Upper("subject"),
                models.OrderBy(models.F("id"), descending=True, nulls_last=True),
                condition=models.Q(("is_channel_message", True)),
                name="zerver_message_realm_upper_subject",
            ),
        ),
        AddIndexConcurrently(
            model_name="message",
            index=models.Index(
                models.F("realm_id"),
                models.F("recipient_id"),
                django.db.models.functions.text.Upper("subject"),
                models.OrderBy(models.F("id"), descending=True, nulls_last=True),
                condition=models.Q(("is_channel_message", True)),
                name="zerver_message_realm_recipient_upper_subject",
            ),
        ),
        AddIndexConcurrently(
            model_name="message",
            index=models.Index(
                models.F("realm_id"),
                models.F("recipient_id"),
                models.F("subject"),
                models.OrderBy(models.F("id"), descending=True, nulls_last=True),
                condition=models.Q(("is_channel_message", True)),
                name="zerver_message_realm_recipient_subject",
            ),
        ),
    ]

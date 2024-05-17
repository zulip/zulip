import django.db.models.functions.text
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0471_alter_realm_create_multiuse_invite_group"),
    ]

    # The non-realm_id-prefixed versions will be removed in the next migration.
    operations = [
        AddIndexConcurrently(
            model_name="message",
            index=models.Index(
                models.F("realm_id"),
                models.F("recipient_id"),
                models.F("id"),
                name="zerver_message_realm_recipient_id",
            ),
        ),
        AddIndexConcurrently(
            model_name="message",
            index=models.Index(
                models.F("realm_id"),
                models.F("recipient_id"),
                models.F("date_sent"),
                name="zerver_message_realm_recipient_date_sent",
            ),
        ),
        AddIndexConcurrently(
            model_name="message",
            index=models.Index(
                models.F("realm_id"),
                models.F("sender_id"),
                models.F("recipient_id"),
                name="zerver_message_realm_sender_recipient",
            ),
        ),
        AddIndexConcurrently(
            model_name="message",
            index=models.Index(
                models.F("realm_id"), models.F("date_sent"), name="zerver_message_realm_date_sent"
            ),
        ),
        AddIndexConcurrently(
            model_name="message",
            index=models.Index(
                models.F("realm_id"),
                django.db.models.functions.text.Upper("subject"),
                models.OrderBy(models.F("id"), descending=True, nulls_last=True),
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
                name="zerver_message_realm_recipient_subject",
            ),
        ),
        AddIndexConcurrently(
            model_name="message",
            index=models.Index(
                models.F("realm_id"),
                models.OrderBy(models.F("id"), descending=True, nulls_last=True),
                name="zerver_message_realm_id",
            ),
        ),
        AddIndexConcurrently(
            model_name="scheduledmessage",
            index=models.Index(
                condition=models.Q(("delivered", False)),
                fields=["realm_id", "sender", "delivery_type", "scheduled_timestamp"],
                name="zerver_realm_unsent_scheduled_messages_by_user",
            ),
        ),
        migrations.RunSQL(
            sql="CREATE STATISTICS IF NOT EXISTS zerver_message_realm_recipient ON realm_id, recipient_id FROM zerver_message",
            reverse_sql="DROP STATISTICS IF EXISTS zerver_message_realm_recipient",
        ),
        migrations.RunSQL(
            sql="CREATE STATISTICS IF NOT EXISTS zerver_message_realm_sender ON realm_id, sender_id FROM zerver_message",
            reverse_sql="DROP STATISTICS IF EXISTS zerver_message_realm_sender",
        ),
        migrations.RunSQL("ANALYZE zerver_message"),
    ]

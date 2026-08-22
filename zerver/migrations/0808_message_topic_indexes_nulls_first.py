import django.db.models.functions.text
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0807_usertopic_zerver_usertopic_user_visibility_recipient_idx"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="message",
            new_name="zerver_message_realm_upper_subject_nulls_last",
            old_name="zerver_message_realm_upper_subject",
        ),
        migrations.RenameIndex(
            model_name="message",
            new_name="zerver_message_realm_recipient_upper_subject_nulls_last",
            old_name="zerver_message_realm_recipient_upper_subject",
        ),
        migrations.RenameIndex(
            model_name="message",
            new_name="zerver_message_realm_recipient_subject_nulls_last",
            old_name="zerver_message_realm_recipient_subject",
        ),
        migrations.RenameIndex(
            model_name="message",
            new_name="zerver_message_realm_id_nulls_last",
            old_name="zerver_message_realm_id",
        ),
        AddIndexConcurrently(
            model_name="message",
            index=models.Index(
                models.F("realm_id"),
                django.db.models.functions.text.Upper("subject"),
                models.OrderBy(models.F("id"), descending=True),
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
                models.OrderBy(models.F("id"), descending=True),
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
                models.OrderBy(models.F("id"), descending=True),
                condition=models.Q(("is_channel_message", True)),
                name="zerver_message_realm_recipient_subject",
            ),
        ),
        AddIndexConcurrently(
            model_name="message",
            index=models.Index(
                models.F("realm_id"),
                models.OrderBy(models.F("id"), descending=True),
                name="zerver_message_realm_id",
            ),
        ),
        # The two indexes above on Upper("subject") are expression
        # indexes, whose per-expression statistics are only collected
        # by ANALYZE; without them the planner cannot estimate the
        # selectivity of a topic lookup.
        migrations.RunSQL(
            sql="ANALYZE zerver_message",
            reverse_sql=migrations.RunSQL.noop,
            elidable=True,
        ),
    ]

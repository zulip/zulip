from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0301_fix_unread_messages_in_deactivated_streams"),
    ]

    operations = [
        # We do Stream lookups case-insensitively with respect to the name, but we were missing
        # the appropriate (realm_id, upper(name::text)) unique index to enforce uniqueness
        # on database level.
        migrations.RunSQL(
            """
            CREATE UNIQUE INDEX zerver_stream_realm_id_name_uniq ON zerver_stream (realm_id, upper(name::text));
        """
        ),
        migrations.AlterUniqueTogether(
            name="stream",
            unique_together=set(),
        ),
    ]

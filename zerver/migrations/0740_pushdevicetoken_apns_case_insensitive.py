import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0739_alter_realm_can_set_delete_message_policy_group"),
    ]

    operations = [
        # Update the last_updated to the max for any set of (user_id, kind=1, lower(token))
        migrations.RunSQL(
            """
            WITH dups AS (
              SELECT user_id, kind, LOWER(token) AS token, MAX(last_updated) AS max_last_updated
                FROM zerver_pushdevicetoken
               WHERE kind = 1
               GROUP BY user_id, kind, LOWER(token)
              HAVING COUNT(*) > 1
            )
            UPDATE zerver_pushdevicetoken
               SET last_updated = dups.max_last_updated
              FROM dups
             WHERE zerver_pushdevicetoken.user_id = dups.user_id
               AND zerver_pushdevicetoken.kind = dups.kind
               AND LOWER(zerver_pushdevicetoken.token) = dups.token
            """
        ),
        # And then delete all but the first of each of those sets
        migrations.RunSQL(
            """
            WITH dups AS (
              SELECT user_id, kind, LOWER(token) AS token, MIN(id) AS min_id
                FROM zerver_pushdevicetoken
               WHERE kind = 1
               GROUP BY user_id, kind, LOWER(token)
              HAVING COUNT(*) > 1
            )
            DELETE FROM zerver_pushdevicetoken
             USING dups
             WHERE zerver_pushdevicetoken.user_id = dups.user_id
               AND zerver_pushdevicetoken.kind = dups.kind
               AND LOWER(zerver_pushdevicetoken.token) = dups.token
               AND zerver_pushdevicetoken.id != dups.min_id
            """
        ),
        migrations.AddConstraint(
            model_name="pushdevicetoken",
            constraint=models.UniqueConstraint(
                models.F("user_id"),
                models.F("kind"),
                django.db.models.functions.text.Lower(models.F("token")),
                condition=models.Q(("kind", 1)),
                name="zerver_pushdevicetoken_apns_user_kind_token",
            ),
        ),
        migrations.AddConstraint(
            model_name="pushdevicetoken",
            constraint=models.UniqueConstraint(
                models.F("user_id"),
                models.F("kind"),
                models.F("token"),
                condition=models.Q(("kind", 2)),
                name="zerver_pushdevicetoken_fcm_user_kind_token",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="pushdevicetoken",
            unique_together=set(),
        ),
    ]

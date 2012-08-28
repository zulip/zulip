import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zilencer", "0066_alter_remotepushdevice_token_kind"),
    ]

    operations = [
        # This parallels zerver/migrations/0740 but must account for
        # the user_id / user_uuid split.
        migrations.RunSQL(
            """
            WITH dups AS (
              SELECT server_id, user_id, kind, LOWER(token) AS token, MAX(last_updated) AS max_last_updated
                FROM zilencer_remotepushdevicetoken
               WHERE kind = 1
                 AND user_uuid IS NULL
               GROUP BY server_id, user_id, kind, LOWER(token)
              HAVING COUNT(*) > 1
            )
            UPDATE zilencer_remotepushdevicetoken
               SET last_updated = dups.max_last_updated
              FROM dups
             WHERE zilencer_remotepushdevicetoken.server_id = dups.server_id
               AND zilencer_remotepushdevicetoken.user_id = dups.user_id
               AND zilencer_remotepushdevicetoken.user_uuid IS NULL
               AND zilencer_remotepushdevicetoken.kind = dups.kind
               AND LOWER(zilencer_remotepushdevicetoken.token) = dups.token
            """
        ),
        migrations.RunSQL(
            """
            WITH dups AS (
              SELECT server_id, user_id, kind, LOWER(token) AS token, MIN(id) AS min_id
                FROM zilencer_remotepushdevicetoken
               WHERE kind = 1
                 AND user_uuid IS NULL
               GROUP BY server_id, user_id, kind, LOWER(token)
              HAVING COUNT(*) > 1
            )
            DELETE FROM zilencer_remotepushdevicetoken
             USING dups
             WHERE zilencer_remotepushdevicetoken.server_id = dups.server_id
               AND zilencer_remotepushdevicetoken.user_id = dups.user_id
               AND zilencer_remotepushdevicetoken.user_uuid IS NULL
               AND zilencer_remotepushdevicetoken.kind = dups.kind
               AND LOWER(zilencer_remotepushdevicetoken.token) = dups.token
               AND zilencer_remotepushdevicetoken.id != dups.min_id
            """
        ),
        migrations.AddConstraint(
            model_name="remotepushdevicetoken",
            constraint=models.UniqueConstraint(
                models.F("server_id"),
                models.F("user_id"),
                models.F("kind"),
                django.db.models.functions.text.Lower(models.F("token")),
                condition=models.Q(("kind", 1)),
                name="zilencer_remotepushdevicetoken_apns_server_user_id_kind_token",
            ),
        ),
        migrations.AddConstraint(
            model_name="remotepushdevicetoken",
            constraint=models.UniqueConstraint(
                models.F("server_id"),
                models.F("user_id"),
                models.F("kind"),
                models.F("token"),
                condition=models.Q(("kind", 2)),
                name="zilencer_remotepushdevicetoken_fcm_server_user_id_kind_token",
            ),
        ),
        migrations.RunSQL(
            """
            WITH dups AS (
              SELECT server_id, user_uuid, kind, LOWER(token) AS token, MAX(last_updated) AS max_last_updated
                FROM zilencer_remotepushdevicetoken
               WHERE kind = 1
                 AND user_id IS NULL
               GROUP BY server_id, user_uuid, kind, LOWER(token)
              HAVING COUNT(*) > 1
            )
            UPDATE zilencer_remotepushdevicetoken
               SET last_updated = dups.max_last_updated
              FROM dups
             WHERE zilencer_remotepushdevicetoken.server_id = dups.server_id
               AND zilencer_remotepushdevicetoken.user_uuid = dups.user_uuid
               AND zilencer_remotepushdevicetoken.user_id IS NULL
               AND zilencer_remotepushdevicetoken.kind = dups.kind
               AND LOWER(zilencer_remotepushdevicetoken.token) = dups.token
            """
        ),
        migrations.RunSQL(
            """
            WITH dups AS (
              SELECT server_id, user_uuid, kind, LOWER(token) AS token, MIN(id) AS min_id
                FROM zilencer_remotepushdevicetoken
               WHERE kind = 1
                 AND user_id IS NULL
               GROUP BY server_id, user_uuid, kind, LOWER(token)
              HAVING COUNT(*) > 1
            )
            DELETE FROM zilencer_remotepushdevicetoken
             USING dups
             WHERE zilencer_remotepushdevicetoken.server_id = dups.server_id
               AND zilencer_remotepushdevicetoken.user_uuid = dups.user_uuid
               AND zilencer_remotepushdevicetoken.user_id IS NULL
               AND zilencer_remotepushdevicetoken.kind = dups.kind
               AND LOWER(zilencer_remotepushdevicetoken.token) = dups.token
               AND zilencer_remotepushdevicetoken.id != dups.min_id
            """
        ),
        migrations.AddConstraint(
            model_name="remotepushdevicetoken",
            constraint=models.UniqueConstraint(
                models.F("server_id"),
                models.F("user_uuid"),
                models.F("kind"),
                django.db.models.functions.text.Lower(models.F("token")),
                condition=models.Q(("kind", 1)),
                name="zilencer_remotepushdevicetoken_apns_server_uuid_kind_token",
            ),
        ),
        migrations.AddConstraint(
            model_name="remotepushdevicetoken",
            constraint=models.UniqueConstraint(
                models.F("server_id"),
                models.F("user_uuid"),
                models.F("kind"),
                models.F("token"),
                condition=models.Q(("kind", 2)),
                name="zilencer_remotepushdevicetoken_fcm_server_uuid_kind_token",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="remotepushdevicetoken",
            unique_together=set(),
        ),
    ]

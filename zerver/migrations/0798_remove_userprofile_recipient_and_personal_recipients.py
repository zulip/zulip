from django.db import connection, migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL

PERSONAL_RECIPIENT_TYPE = 1
BATCH_SIZE = 5000


def delete_personal_recipient_data(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Delete Subscription rows and then Recipient rows for personal recipients.

    Done in batches to avoid long-running transactions on large
    deployments. Both loops are idempotent: re-running simply continues
    deleting whatever rows remain.
    """
    with connection.cursor() as cursor:
        while True:
            cursor.execute(
                SQL(
                    """
                    DELETE FROM zerver_subscription
                    WHERE id IN (
                        SELECT s.id FROM zerver_subscription s
                        JOIN zerver_recipient r ON s.recipient_id = r.id
                        WHERE r.type = %s
                        LIMIT %s
                    )
                    """
                ),
                [PERSONAL_RECIPIENT_TYPE, BATCH_SIZE],
            )
            if cursor.rowcount == 0:
                break

        while True:
            cursor.execute(
                SQL(
                    """
                    DELETE FROM zerver_recipient
                    WHERE id IN (
                        SELECT id FROM zerver_recipient
                        WHERE type = %s
                        LIMIT %s
                    )
                    """
                ),
                [PERSONAL_RECIPIENT_TYPE, BATCH_SIZE],
            )
            if cursor.rowcount == 0:
                break


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0797_userprofile_is_deleted"),
    ]

    operations = [
        # Drop the column via DROP COLUMN IF EXISTS to make the migration idempotent
        # and easier to re-run if needed. This is sometimes necessary for self-hosters
        # that improperly ran user_profile.delete() in the past and thus experience
        # DELETE FROM zerver_recipient crashes later in the migration. In such cases,
        # some db surgery and re-run of the migration is needed.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "ALTER TABLE zerver_userprofile DROP COLUMN IF EXISTS recipient_id",
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name="userprofile",
                    name="recipient",
                ),
            ],
        ),
        migrations.RunPython(
            delete_personal_recipient_data,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]

from django.db import connection, migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

SUCCEEDED = 3
EXPORT_FROM_PRIOR_SERVER = 6


def restore_command_line_export_status(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    # The original version of migration 0801 flipped every SUCCEEDED row
    # without an export_path to EXPORT_FROM_PRIOR_SERVER, incorrectly
    # including command-line (manage.py export) exports, which have no
    # acting_user. Restore those rows to SUCCEEDED.
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE zerver_realmexport
            SET status = %s
            WHERE status = %s AND acting_user_id IS NULL
            RETURNING id, realm_id
            """,
            [SUCCEEDED, EXPORT_FROM_PRIOR_SERVER],
        )
        for export_id, realm_id in cursor.fetchall():
            print(
                f"Restored RealmExport id={export_id} realm_id={realm_id}: "
                f"EXPORT_FROM_PRIOR_SERVER -> SUCCEEDED"
            )


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0801_realmexport_backfill_export_from_prior_server_status"),
    ]

    operations = [
        migrations.RunPython(
            restore_command_line_export_status,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]

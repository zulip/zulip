from django.db import connection, migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

SUCCEEDED = 3
EXPORT_FROM_PRIOR_SERVER = 6


def backfill_export_from_prior_server_status(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    # RealmExport rows with SUCCEEDED status and no export_path, created
    # via the UI, are records carried across a realm export->import, where
    # the tarball is not preserved. Fix them up to use the
    # EXPORT_FROM_PRIOR_SERVER status. Exports created via the manage.py
    # export command have no acting_user and likewise lack an export_path,
    # but they are not surfaced via the UI/API, so we leave them untouched.
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE zerver_realmexport
            SET status = %s
            WHERE status = %s AND export_path IS NULL AND acting_user_id IS NOT NULL
            RETURNING id, realm_id
            """,
            [EXPORT_FROM_PRIOR_SERVER, SUCCEEDED],
        )
        for export_id, realm_id in cursor.fetchall():
            print(
                f"Fixed RealmExport id={export_id} realm_id={realm_id}: "
                f"SUCCEEDED -> EXPORT_FROM_PRIOR_SERVER"
            )


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0800_cleanup_case_mismatched_legacy_apns_tokens"),
    ]

    operations = [
        migrations.RunPython(
            backfill_export_from_prior_server_status,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]

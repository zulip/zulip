from django.db import connection, migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def fill_new_columns(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    UserPresence = apps.get_model("zerver", "UserPresence")

    # In theory, we'd like to preserve the distinction between the
    # IDLE and ACTIVE statuses in legacy data.  However, there is no
    # correct way to do so; the previous data structure only stored
    # the current IDLE/ACTIVE status of the last update for each
    # (user, client) pair. There's no way to know whether the last
    # time the user had the other status with that client was minutes
    # or months beforehand.
    #
    # So the only sane thing we can do with this migration is to treat
    # the last presence update as having been a PRESENCE_ACTIVE_STATUS
    # event. This will result in some currently-idle users being
    # incorrectly recorded as having been active at the last moment
    # that they were idle before this migration.  This error is
    # unlikely to be significant in practice, and in any case is an
    # unavoidable flaw caused by the legacy previous data model.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT realm_id, user_profile_id, MAX(timestamp) FROM zerver_userpresenceold WHERE status IN (1, 2) GROUP BY realm_id, user_profile_id"
        )
        latest_presence_per_user = cursor.fetchall()

    UserPresence.objects.bulk_create(
        [
            UserPresence(
                user_profile_id=presence_row[1],
                realm_id=presence_row[0],
                last_connected_time=presence_row[2],
                last_active_time=presence_row[2],
            )
            for presence_row in latest_presence_per_user
        ],
        # Limit the size of individual network requests for very large
        # servers.
        batch_size=10000,
        # If the UserPresence worker has already started, or a user
        # has changed their invisible status while migrations are
        # running, then some UserPresence rows may exist. Those will
        # generally be newer than what we have here, so ignoring
        # conflicts so we can complete backfilling users who don't
        # have more current data is the right resolution.
        ignore_conflicts=True,
    )


def clear_new_columns(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    UserPresence = apps.get_model("zerver", "UserPresence")
    UserPresence.objects.all().delete()


class Migration(migrations.Migration):
    """
    Ports data from the UserPresence model into the new one.
    """

    atomic = False

    dependencies = [
        ("zerver", "0443_userpresence_new_table_schema"),
    ]

    operations = [migrations.RunPython(fill_new_columns, reverse_code=clear_new_columns)]

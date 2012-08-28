from django.contrib.postgres.operations import AddIndexConcurrently, RemoveIndexConcurrently
from django.db import connection, migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL


def clear_old_data_for_unused_usermessage_flags(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Because 'topic_wildcard_mentioned' and 'group_mentioned' flags are
    reused flag slots (ref: c37871a) in the 'flags' bitfield, we're not
    confident that their value is in 0 state on very old servers, and this
    migration is to ensure that's the case.
    Additionally, we are clearing 'force_expand' and 'force_collapse' unused
    flags to save future work.
    """
    with connection.cursor() as cursor:
        cursor.execute(SQL("SELECT MAX(id) FROM zerver_usermessage WHERE flags & 480 <> 0;"))
        (max_id,) = cursor.fetchone()

    # nothing to update
    if not max_id:
        return

    BATCH_SIZE = 5000
    lower_id_bound = 0
    while lower_id_bound < max_id:
        upper_id_bound = min(lower_id_bound + BATCH_SIZE, max_id)
        with connection.cursor() as cursor:
            query = SQL(
                """
                    UPDATE zerver_usermessage
                    SET flags = (flags & ~(1 << 5) & ~(1 << 6) & ~(1 << 7) & ~(1 << 8))
                    WHERE flags & 480 <> 0
                    AND id > %(lower_id_bound)s AND id <= %(upper_id_bound)s;
            """
            )
            cursor.execute(
                query,
                {"lower_id_bound": lower_id_bound, "upper_id_bound": upper_id_bound},
            )

        print(f"Processed {upper_id_bound} / {max_id}")
        lower_id_bound += BATCH_SIZE


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("zerver", "0485_alter_usermessage_flags_and_add_index"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="usermessage",
            index=models.Index(
                "id",
                condition=models.Q(("flags__andnz", 480)),
                name="zerver_usermessage_temp_clear_flags",
            ),
        ),
        migrations.RunPython(
            clear_old_data_for_unused_usermessage_flags,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
        RemoveIndexConcurrently(
            model_name="usermessage",
            name="zerver_usermessage_temp_clear_flags",
        ),
    ]

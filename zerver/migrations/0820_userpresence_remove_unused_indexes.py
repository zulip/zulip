import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import connection, migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL, Identifier

from zerver.lib.migrate import remove_index


def remove_single_column_indexes(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    # These indexes come from db_index=True and the ForeignKey default
    # rather than Meta.indexes, so remove_index can't drop them.
    if settings.MIGRATIONS_ADD_REMOVE_INDEXES_CONCURRENTLY:
        drop_index = SQL("DROP INDEX CONCURRENTLY IF EXISTS {index_name}")
    else:
        drop_index = SQL("DROP INDEX IF EXISTS {index_name}")

    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, "zerver_userpresence")
        for index_name, infodict in constraints.items():
            if not infodict["index"] or infodict["unique"] or infodict["primary_key"]:
                continue
            if infodict["columns"] not in (
                ["realm_id"],
                ["last_update_id"],
                ["last_connected_time"],
                ["last_active_time"],
            ):
                continue
            print(f"dropping index {index_name}")
            cursor.execute(drop_index.format(index_name=Identifier(index_name)))


class Migration(migrations.Migration):
    atomic = not settings.MIGRATIONS_ADD_REMOVE_INDEXES_CONCURRENTLY

    dependencies = [
        ("zerver", "0819_userpresence_last_active_time_user_profile_id_idx"),
    ]

    operations = [
        remove_index(
            model_name="userpresence",
            name="zerver_userpresence_realm_id_last_active_time_1c5aa9a2_idx",
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    remove_single_column_indexes,
                    reverse_code=migrations.RunPython.noop,
                    elidable=True,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="userpresence",
                    name="realm",
                    field=models.ForeignKey(
                        db_index=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="zerver.realm",
                    ),
                ),
                migrations.AlterField(
                    model_name="userpresence",
                    name="last_update_id",
                    field=models.PositiveBigIntegerField(default=0),
                ),
                migrations.AlterField(
                    model_name="userpresence",
                    name="last_connected_time",
                    field=models.DateTimeField(default=django.utils.timezone.now, null=True),
                ),
                migrations.AlterField(
                    model_name="userpresence",
                    name="last_active_time",
                    field=models.DateTimeField(default=django.utils.timezone.now, null=True),
                ),
            ],
        ),
    ]

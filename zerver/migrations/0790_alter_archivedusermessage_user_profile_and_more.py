import django.db.models.deletion
from django.conf import settings
from django.db import connection, migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL, Identifier

from zerver.lib.partial import partial


def remove_index_concurrently_by_table_and_column(
    model_name: str, column_name: str, apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    with connection.cursor() as cursor:
        for name, definition in connection.introspection.get_constraints(
            cursor, f"zerver_{model_name}"
        ).items():
            if not definition["index"]:
                continue
            if definition["columns"] != [column_name]:
                continue
            cursor.execute(
                SQL("DROP INDEX CONCURRENTLY {indexname}").format(
                    indexname=Identifier(name),
                )
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0789_add_external_auth_fields_to_preregistrationuser"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    partial(
                        remove_index_concurrently_by_table_and_column,
                        "archivedusermessage",
                        "user_profile_id",
                    ),
                ),
                migrations.RunPython(
                    partial(
                        remove_index_concurrently_by_table_and_column,
                        "usermessage",
                        "user_profile_id",
                    ),
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="archivedusermessage",
                    name="user_profile",
                    field=models.ForeignKey(
                        db_index=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                migrations.AlterField(
                    model_name="usermessage",
                    name="user_profile",
                    field=models.ForeignKey(
                        db_index=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]

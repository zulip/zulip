import django.db.models.deletion
from django.db import connection, migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.backends.utils import names_digest
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL, Identifier

from zerver.lib.partial import partial


def add_unique_and_remove_non_unique_index(
    table_name: str,
    apps: StateApps,
    schema_editor: BaseDatabaseSchemaEditor,
) -> None:
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table_name)
        unique_constraint_name = (
            f"{table_name}_recipient_id_{names_digest(table_name, 'recipient_id', length=8)}_uniq"
        )

        existing = constraints.get(unique_constraint_name)
        if existing is None:
            # Create unique index concurrently (non-blocking).
            cursor.execute(
                SQL("CREATE UNIQUE INDEX CONCURRENTLY {name} ON {table} (recipient_id)").format(
                    table=Identifier(table_name),
                    name=Identifier(unique_constraint_name),
                )
            )
            # Promote to a table constraint (instant metadata operation).
            cursor.execute(
                SQL("ALTER TABLE {table} ADD CONSTRAINT {name} UNIQUE USING INDEX {name}").format(
                    table=Identifier(table_name),
                    name=Identifier(unique_constraint_name),
                )
            )
        elif existing.get("index"):
            # Index was created but not yet promoted (crash between steps).
            cursor.execute(
                SQL("ALTER TABLE {table} ADD CONSTRAINT {name} UNIQUE USING INDEX {name}").format(
                    table=Identifier(table_name),
                    name=Identifier(unique_constraint_name),
                )
            )

        for name, info in constraints.items():
            if info["columns"] != ["recipient_id"]:
                continue
            if info["unique"]:
                continue
            if not info.get("index"):
                continue
            cursor.execute(
                SQL("DROP INDEX CONCURRENTLY IF EXISTS {name}").format(
                    name=Identifier(name),
                )
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0793_alter_directmessagegroup_huddle_hash_and_more"),
    ]

    operations = [
        # Prevent the naive plan of dropping and re-creating the
        # foreign key constraint, and create the unique constraint
        # before dropping the non-unique index.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    partial(
                        add_unique_and_remove_non_unique_index,
                        "zerver_huddle",
                    ),
                ),
                migrations.RunPython(
                    partial(
                        add_unique_and_remove_non_unique_index,
                        "zerver_stream",
                    ),
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="directmessagegroup",
                    name="recipient",
                    field=models.OneToOneField(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="zerver.recipient",
                    ),
                ),
                migrations.AlterField(
                    model_name="stream",
                    name="recipient",
                    field=models.OneToOneField(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="zerver.recipient",
                    ),
                ),
            ],
        ),
    ]

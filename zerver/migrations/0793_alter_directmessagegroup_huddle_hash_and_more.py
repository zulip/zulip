from django.db import connection, migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL, Identifier


def remove_non_unique_indexes(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    # We have to do this with inspection because the index name is not
    # consistent across versions, and RemoveIndexConcurrently takes an
    # index name.
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, "zerver_huddle")
        for index_name, infodict in constraints.items():
            if infodict["columns"] != ["huddle_hash"]:
                continue
            if infodict["unique"]:
                continue
            raw_query = SQL("DROP INDEX CONCURRENTLY IF EXISTS {index_name}").format(
                index_name=Identifier(index_name)
            )
            cursor.execute(raw_query)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0792_fix_animated_emoji_still_images"),
    ]

    operations = [
        # Prevent the naive plan of dropping and re-creating the unique index
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(remove_non_unique_indexes),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="directmessagegroup",
                    name="huddle_hash",
                    field=models.CharField(max_length=40),
                ),
                migrations.AddConstraint(
                    model_name="directmessagegroup",
                    constraint=models.UniqueConstraint(
                        fields=("huddle_hash",), name="zerver_huddle_huddle_hash_key"
                    ),
                ),
            ],
        ),
    ]

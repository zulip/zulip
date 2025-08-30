from django.db import connection, migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL

from zerver.lib.migrate import do_batch_update


def update_stream_default_code_block_language(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    stream = apps.get_model("zerver", "Stream")
    with connection.cursor() as cursor:
        do_batch_update(
            cursor,
            stream._meta.db_table,
            [
                SQL(
                    "default_code_block_language = (SELECT default_code_block_language FROM zerver_realm WHERE id = realm_id)"
                )
            ],
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0752_stream_default_code_block_language"),
    ]

    operations = [
        migrations.RunPython(
            update_stream_default_code_block_language,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        )
    ]

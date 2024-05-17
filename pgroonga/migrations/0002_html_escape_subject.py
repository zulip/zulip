from django.db import connection, migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL

from zerver.lib.migrate import do_batch_update


def rebuild_pgroonga_index(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    with connection.cursor() as cursor:
        do_batch_update(
            cursor,
            "zerver_message",
            [SQL("search_pgroonga = escape_html(subject) || ' ' || rendered_content")],
            batch_size=10000,
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("pgroonga", "0001_enable"),
    ]

    operations = [
        migrations.RunPython(rebuild_pgroonga_index, reverse_code=migrations.RunPython.noop),
    ]

from django.db import connection, migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL

from zerver.lib.migrate import do_batch_update


def update_is_channel_message(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Message = apps.get_model("zerver", "Message")
    ArchivedMessage = apps.get_model("zerver", "ArchivedMessage")

    with connection.cursor() as cursor:
        for message_model in [Message, ArchivedMessage]:
            do_batch_update(
                cursor,
                message_model._meta.db_table,
                [
                    SQL(
                        "is_channel_message = (SELECT type = 2 FROM zerver_recipient WHERE zerver_recipient.id = recipient_id)"
                    )
                ],
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0690_message_is_channel_message"),
    ]

    operations = [
        migrations.RunPython(
            update_is_channel_message, reverse_code=migrations.RunPython.noop, elidable=True
        )
    ]

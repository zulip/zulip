from django.db import connection, migrations
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps


def mark_messages_read(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    Stream = apps.get_model("zerver", "Stream")
    deactivated_stream_ids = list(Stream.objects.filter(deactivated=True).values_list('id', flat=True))
    with connection.cursor() as cursor:
        for i in deactivated_stream_ids:
            cursor.execute(f"""
                UPDATE zerver_usermessage SET flags = flags | 1
                FROM zerver_message
                INNER JOIN zerver_stream ON zerver_stream.recipient_id = zerver_message.recipient_id
                WHERE zerver_message.id = zerver_usermessage.message_id
                AND zerver_stream.id = {i};
            """)

class Migration(migrations.Migration):
    """
    We're changing the stream deactivation process to make it mark all messages
    in the stream as read. For things to be consistent with streams that have been
    deactivated before this change, we need a migration to fix those old streams,
    to have all messages marked as read.
    """
    atomic = False

    dependencies = [
        ('zerver', '0300_add_attachment_is_web_public'),
    ]

    operations = [
        migrations.RunPython(mark_messages_read, reverse_code=migrations.RunPython.noop),
    ]

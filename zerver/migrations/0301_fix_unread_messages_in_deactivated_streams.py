from django.db import migrations


class Migration(migrations.Migration):
    """
    We're changing the stream deactivation process to make it mark all messages
    in the stream as read. For things to be consistent with streams that have been
    deactivated before this change, we need a migration to fix those old streams,
    to have all messages marked as read.
    """

    dependencies = [
        ("zerver", "0300_add_attachment_is_web_public"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                UPDATE zerver_usermessage SET flags = flags | 1
                FROM zerver_message
                INNER JOIN zerver_stream ON zerver_stream.recipient_id = zerver_message.recipient_id
                WHERE zerver_message.id = zerver_usermessage.message_id
                AND zerver_stream.deactivated;
            """,
            reverse_sql="",
            elidable=True,
        ),
    ]

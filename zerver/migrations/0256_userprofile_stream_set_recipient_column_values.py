from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0255_userprofile_stream_add_recipient_column"),
    ]

    operations = [
        migrations.RunSQL(
            """
            UPDATE zerver_userprofile
            SET recipient_id = zerver_recipient.id
            FROM zerver_recipient
            WHERE zerver_recipient.type_id = zerver_userprofile.id AND zerver_recipient.type = 1;
            """,
            reverse_sql="UPDATE zerver_userprofile SET recipient_id = NULL",
            elidable=True,
        ),
        migrations.RunSQL(
            """
            UPDATE zerver_stream
            SET recipient_id = zerver_recipient.id
            FROM zerver_recipient
            WHERE zerver_recipient.type_id = zerver_stream.id AND zerver_recipient.type = 2;
            """,
            reverse_sql="UPDATE zerver_stream SET recipient_id = NULL",
            elidable=True,
        ),
    ]

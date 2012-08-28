from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0270_huddle_recipient"),
    ]

    operations = [
        migrations.RunSQL(
            """
            UPDATE zerver_huddle
            SET recipient_id = zerver_recipient.id
            FROM zerver_recipient
            WHERE zerver_recipient.type_id = zerver_huddle.id AND zerver_recipient.type = 3;
            """,
            reverse_sql="UPDATE zerver_huddle SET recipient_id = NULL",
            elidable=True,
        ),
    ]

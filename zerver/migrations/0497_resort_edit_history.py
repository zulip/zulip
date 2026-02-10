from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0496_alter_scheduledmessage_read_by_sender"),
    ]

    operations = [
        migrations.RunSQL(
            # Update with properly-sorted history for messages changed
            # after 5c96f942060e was merged.
            """
            WITH sorted_history AS (
                SELECT zerver_message.id AS rowid,
                       JSONB_AGG(value ORDER BY (value->>'timestamp')::NUMERIC desc) AS updated_history
                FROM zerver_message
                    CROSS JOIN JSONB_ARRAY_ELEMENTS(zerver_message.edit_history::jsonb)
                WHERE zerver_message.edit_history IS NOT NULL
                  AND zerver_message.last_edit_time > '2024-02-14'
                  AND JSONB_ARRAY_LENGTH(zerver_message.edit_history::jsonb) > 1
                GROUP BY zerver_message.id
                ORDER BY zerver_message.id
            )
            UPDATE zerver_message
                SET edit_history = sorted_history.updated_history::text
            FROM sorted_history
            WHERE zerver_message.id = sorted_history.rowid
              AND zerver_message.edit_history::jsonb != sorted_history.updated_history
            """,
            reverse_sql="",
            elidable=True,
        )
    ]

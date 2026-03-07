from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0744_alter_channelfolder_name"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS fts_update_log_message_id
                ON fts_update_log(message_id)
            """,
            reverse_sql="""
                DROP INDEX CONCURRENTLY IF EXISTS fts_update_log_message_id
            """,
        ),
    ]

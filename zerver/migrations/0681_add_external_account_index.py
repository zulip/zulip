from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        (
            "zerver",
            "0680_rename_general_chat_to_empty_string_topic",
        ),  # Replace with actual previous migration
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE INDEX zerver_customprofilefieldvalue_field_id_value_idx
            ON zerver_customprofilefieldvalue (field_id, value);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS zerver_customprofilefieldvalue_field_id_value_idx;
            """,
        )
    ]

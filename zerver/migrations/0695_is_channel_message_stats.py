from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0694_remove_message_unconditional_topic_indexes"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE STATISTICS IF NOT EXISTS zerver_message_subject_is_channel_message ON subject, is_channel_message FROM zerver_message",
            reverse_sql="DROP STATISTICS IF EXISTS zerver_message_subject_is_channel_message",
        ),
        migrations.RunSQL(
            sql="ALTER STATISTICS zerver_message_subject_is_channel_message SET STATISTICS 1500",
            reverse_sql="ALTER STATISTICS zerver_message_subject_is_channel_message SET STATISTICS -1",
        ),
        migrations.RunSQL("ANALYZE zerver_message"),
    ]

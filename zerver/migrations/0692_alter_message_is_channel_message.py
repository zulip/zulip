from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0691_backfill_message_is_channel_message"),
    ]

    operations = [
        migrations.AlterField(
            model_name="archivedmessage",
            name="is_channel_message",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AlterField(
            model_name="message",
            name="is_channel_message",
            field=models.BooleanField(db_index=True, default=True),
        ),
    ]

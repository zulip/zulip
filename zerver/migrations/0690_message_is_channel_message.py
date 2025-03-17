from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0689_mark_navigation_tour_video_as_read"),
    ]

    operations = [
        migrations.AddField(
            model_name="archivedmessage",
            name="is_channel_message",
            field=models.BooleanField(db_index=True, default=True, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="is_channel_message",
            field=models.BooleanField(db_index=True, default=True, null=True),
        ),
    ]

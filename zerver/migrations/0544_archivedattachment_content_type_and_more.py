from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0543_move_emoji_images"),
    ]

    operations = [
        migrations.AddField(
            model_name="archivedattachment",
            name="content_type",
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name="attachment",
            name="content_type",
            field=models.TextField(null=True),
        ),
    ]

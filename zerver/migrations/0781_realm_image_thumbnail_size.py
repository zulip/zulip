from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0780_delete_pushdevice"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="media_preview_size",
            field=models.PositiveSmallIntegerField(default=100),
        ),
    ]

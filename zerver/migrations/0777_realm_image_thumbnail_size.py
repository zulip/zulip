from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0776_realm_default_avatar_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="image_thumbnail_size",
            field=models.PositiveSmallIntegerField(default=10),
        ),
    ]

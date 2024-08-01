import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0553_copy_emoji_images"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImageAttachment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("path_id", models.TextField(db_index=True, unique=True)),
                ("original_width_px", models.IntegerField()),
                ("original_height_px", models.IntegerField()),
                ("frames", models.IntegerField()),
                ("thumbnail_metadata", models.JSONField(default=list)),
                (
                    "realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="zerver.realm"
                    ),
                ),
            ],
        ),
    ]

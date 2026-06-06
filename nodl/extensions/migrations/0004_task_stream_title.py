"""Store nodl task display title on task stream extensions."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("extensions", "0003_task_stream_and_realm_user_extensions"),
    ]

    operations = [
        migrations.AddField(
            model_name="nodltaskstreamextension",
            name="task_title",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]

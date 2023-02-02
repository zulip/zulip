from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0044_reaction"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="waiting_period_threshold",
            field=models.PositiveIntegerField(default=0),
        ),
    ]

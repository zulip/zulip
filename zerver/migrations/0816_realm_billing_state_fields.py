from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0815_merge"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="non_workplace_pricing_eligible",
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AddField(
            model_name="realm",
            name="on_discounted_plan",
            field=models.BooleanField(db_default=False, default=False),
        ),
    ]

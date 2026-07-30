from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("corporate", "0047_customerplan_unique_never_started_plan_customer_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="licenseledger",
            name="external_licenses",
            field=models.IntegerField(db_default=0, default=0),
        ),
        migrations.AddField(
            model_name="licenseledger",
            name="external_licenses_at_next_renewal",
            field=models.IntegerField(db_default=0, default=0),
        ),
    ]

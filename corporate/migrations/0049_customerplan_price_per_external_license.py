from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("corporate", "0048_licenseledger_external_licenses"),
    ]

    operations = [
        migrations.AddField(
            model_name="customerplan",
            name="price_per_external_license",
            field=models.IntegerField(null=True),
        ),
    ]

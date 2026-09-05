from django.db import migrations, models


class Migration(migrations.Migration):
    """
    The AlterField operations pin db_column to the existing column names, and
    come first so that the subsequent RenameField operations see identical old
    and new column names and therefore there is no DB schema change.
    """

    dependencies = [
        ("corporate", "0047_customerplan_unique_never_started_plan_customer_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="licenseledger",
            name="licenses",
            field=models.IntegerField(db_column="licenses"),
        ),
        migrations.AlterField(
            model_name="licenseledger",
            name="licenses_at_next_renewal",
            field=models.IntegerField(db_column="licenses_at_next_renewal", null=True),
        ),
        migrations.RenameField(
            model_name="licenseledger",
            old_name="licenses",
            new_name="workplace_licenses",
        ),
        migrations.RenameField(
            model_name="licenseledger",
            old_name="licenses_at_next_renewal",
            new_name="workplace_licenses_at_next_renewal",
        ),
    ]

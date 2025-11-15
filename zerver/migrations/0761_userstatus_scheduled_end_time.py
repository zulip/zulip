from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "zerver",
            "0760_preregistrationuser_is_realm_importer",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="userstatus",
            name="scheduled_end_time",
            field=models.DateTimeField(db_index=True, null=True),
        ),
    ]

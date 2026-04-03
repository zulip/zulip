from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0801_realmexport_backfill_export_from_prior_server_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="stream",
            name="push_notifications_enabled",
            field=models.BooleanField(default=False, db_default=False),
        ),
    ]

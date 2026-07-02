from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0801_realmexport_backfill_export_from_prior_server_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmuserdefault",
            name="file_preview_extensions",
            field=models.TextField(default=""),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="file_preview_extensions",
            field=models.TextField(default=""),
        ),
    ]

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "zerver",
            "0801_realmexport_backfill_export_from_prior_server_status",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="stream",
            name="can_access_stream_topics_group",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="+",
                to="zerver.usergroup",
            ),
        ),
    ]

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "zerver",
            "0585_userprofile_allow_private_data_export_and_more",
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

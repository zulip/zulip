import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "zerver",
            "0562_remove_realm_create_web_public_stream_policy",
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

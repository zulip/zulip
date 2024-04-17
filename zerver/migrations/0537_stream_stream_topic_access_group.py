import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "zerver",
            "0536_add_message_type",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="stream",
            name="stream_topic_access_group",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="+",
                to="zerver.usergroup",
            ),
        ),
    ]

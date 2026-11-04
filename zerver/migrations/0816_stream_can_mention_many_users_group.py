import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0815_merge"),
    ]

    operations = [
        migrations.AddField(
            model_name="stream",
            name="can_mention_many_users_group",
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="+",
                to="zerver.usergroup",
            ),
        ),
    ]

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0812_delete_inaccessible_user_topics"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="can_bots_invite_users_group",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="+",
                to="zerver.usergroup",
            ),
        ),
    ]

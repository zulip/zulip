import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0814_set_default_for_can_bots_invite_users_group"),
    ]

    operations = [
        migrations.AlterField(
            model_name="realm",
            name="can_bots_invite_users_group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="+",
                to="zerver.usergroup",
            ),
        ),
    ]

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0808_set_default_value_for_stream_can_mention_many_users_group"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stream",
            name="can_mention_many_users_group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="+",
                to="zerver.usergroup",
            ),
        ),
    ]

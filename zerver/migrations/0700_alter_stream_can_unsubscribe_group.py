# Generated by Django 5.1.7 on 2025-04-02 06:01

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0699_set_default_for_stream_can_unsubscribe_group"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stream",
            name="can_unsubscribe_group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="+",
                to="zerver.usergroup",
            ),
        ),
    ]

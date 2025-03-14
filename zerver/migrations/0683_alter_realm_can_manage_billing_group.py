# Generated by Django 5.0.10 on 2025-02-17 16:18

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0682_set_default_value_for_can_manage_billing_group"),
    ]

    operations = [
        migrations.AlterField(
            model_name="realm",
            name="can_manage_billing_group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="+",
                to="zerver.usergroup",
            ),
        ),
    ]

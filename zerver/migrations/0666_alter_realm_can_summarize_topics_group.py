# Generated by Django 5.0.10 on 2025-02-10 10:36

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0665_set_default_for_can_summarize_topics_group"),
    ]

    operations = [
        migrations.AlterField(
            model_name="realm",
            name="can_summarize_topics_group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="+",
                to="zerver.usergroup",
            ),
        ),
    ]

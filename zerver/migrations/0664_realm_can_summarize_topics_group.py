# Generated by Django 5.0.10 on 2025-02-10 10:31

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0663_realm_enable_guest_user_dm_warning"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="can_summarize_topics_group",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="+",
                to="zerver.usergroup",
            ),
        ),
    ]

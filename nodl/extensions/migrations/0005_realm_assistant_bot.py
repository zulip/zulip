"""Add the realm-scoped nodl Assistant bot reference (Epic 2, Story 2.1)."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("extensions", "0004_task_stream_title"),
        ("zerver", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="nodlrealmextension",
            name="assistant_bot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assistant_bot_realm_extensions",
                to="zerver.userprofile",
            ),
        ),
    ]

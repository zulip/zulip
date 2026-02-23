"""Migration for nodl_realm_extension table.

This extension table links Zulip realms to nodl workspaces with sync state tracking.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0001_initial"),
        ("extensions", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="NodlRealmExtension",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "zulip_realm",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="nodl_extension",
                        to="zerver.realm",
                    ),
                ),
                (
                    "nodl_workspace_id",
                    models.UUIDField(unique=True),
                ),
                (
                    "telegram_enabled",
                    models.BooleanField(default=False),
                ),
                (
                    "telegram_bot_token_encrypted",
                    models.TextField(blank=True, null=True),
                ),
                (
                    "sync_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("syncing", "Syncing"),
                            ("synced", "Synced"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "sync_error",
                    models.TextField(blank=True, null=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "last_synced_at",
                    models.DateTimeField(blank=True, null=True),
                ),
            ],
            options={
                "db_table": "nodl_realm_extension",
            },
        ),
        migrations.AddIndex(
            model_name="nodlrealmextension",
            index=models.Index(
                fields=["nodl_workspace_id"],
                name="idx_nodl_realm_ext_workspace",
            ),
        ),
        migrations.AddIndex(
            model_name="nodlrealmextension",
            index=models.Index(
                fields=["sync_status"],
                name="idx_nodl_realm_ext_status",
            ),
        ),
    ]

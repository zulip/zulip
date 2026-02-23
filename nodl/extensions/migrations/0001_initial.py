"""Initial migration for nodl_user_extension table."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("zerver", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="NodlUserExtension",
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
                    "supabase_user_id",
                    models.UUIDField(unique=True),
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
                    "sync_attempts",
                    models.IntegerField(default=0),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "last_synced_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "version",
                    models.IntegerField(default=1),
                ),
                (
                    "zulip_user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="nodl_extension",
                        to="zerver.userprofile",
                        null=True,
                        blank=True,
                    ),
                ),
            ],
            options={
                "db_table": "nodl_user_extension",
            },
        ),
        migrations.AddIndex(
            model_name="nodluserextension",
            index=models.Index(
                fields=["supabase_user_id"],
                name="idx_nodl_user_ext_supabase_id",
            ),
        ),
        migrations.AddIndex(
            model_name="nodluserextension",
            index=models.Index(
                fields=["sync_status"],
                name="idx_nodl_user_ext_sync_status",
            ),
        ),
    ]

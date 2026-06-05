"""Add task stream and realm-scoped user extension tables."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0001_initial"),
        ("extensions", "0002_add_nodl_realm_extension"),
    ]

    operations = [
        migrations.CreateModel(
            name="NodlRealmUserExtension",
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
                ("supabase_user_id", models.UUIDField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                (
                    "zulip_realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="nodl_user_extensions",
                        to="zerver.realm",
                    ),
                ),
                (
                    "zulip_user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="nodl_realm_user_extension",
                        to="zerver.userprofile",
                    ),
                ),
            ],
            options={"db_table": "nodl_realm_user_extension"},
        ),
        migrations.CreateModel(
            name="NodlTaskStreamExtension",
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
                ("nodl_workspace_id", models.UUIDField()),
                ("nodl_task_id", models.UUIDField(unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                (
                    "zulip_realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="nodl_task_streams",
                        to="zerver.realm",
                    ),
                ),
                (
                    "zulip_stream",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="nodl_task_extension",
                        to="zerver.stream",
                    ),
                ),
            ],
            options={"db_table": "nodl_task_stream_extension"},
        ),
        migrations.AddConstraint(
            model_name="nodlrealmuserextension",
            constraint=models.UniqueConstraint(
                fields=("zulip_realm", "supabase_user_id"),
                name="uq_nodl_realm_user_supabase",
            ),
        ),
        migrations.AddIndex(
            model_name="nodlrealmuserextension",
            index=models.Index(
                fields=["supabase_user_id"],
                name="idx_nodl_realm_user_supabase",
            ),
        ),
        migrations.AddIndex(
            model_name="nodlrealmuserextension",
            index=models.Index(
                fields=["zulip_realm", "supabase_user_id"],
                name="idx_nodl_realm_user_lookup",
            ),
        ),
        migrations.AddConstraint(
            model_name="nodltaskstreamextension",
            constraint=models.UniqueConstraint(
                fields=("nodl_workspace_id", "nodl_task_id"),
                name="uq_nodl_task_stream_workspace_task",
            ),
        ),
        migrations.AddIndex(
            model_name="nodltaskstreamextension",
            index=models.Index(
                fields=["nodl_workspace_id"],
                name="idx_nodl_task_stream_workspace",
            ),
        ),
        migrations.AddIndex(
            model_name="nodltaskstreamextension",
            index=models.Index(
                fields=["nodl_task_id"],
                name="idx_nodl_task_stream_task",
            ),
        ),
    ]

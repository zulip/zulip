import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0001_initial"),
        ("nodl", "0001_registration_pin"),
    ]

    operations = [
        migrations.CreateModel(
            name="NodlInvite",
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
                ("invited_phone_hash", models.CharField(max_length=64, db_index=True)),
                ("invited_phone_display", models.CharField(max_length=8)),
                (
                    "invited_user",
                    models.ForeignKey(
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="received_invites",
                        to="zerver.userprofile",
                    ),
                ),
                (
                    "inviter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sent_invites",
                        to="zerver.userprofile",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "expires_at",
                    models.DateTimeField(),
                ),
            ],
            options={
                "db_table": "nodl_invite",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="nodlinvite",
            index=models.Index(
                fields=["inviter", "-created_at"],
                name="idx_nodl_invite_inviter",
            ),
        ),
    ]

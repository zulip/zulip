import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("nodl", "0002_nodl_invite"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CallRecord",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("room_name", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ringing", "Ringing"),
                            ("connected", "Connected"),
                            ("ended", "Ended"),
                            ("missed", "Missed"),
                            ("declined", "Declined"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="ringing",
                        max_length=20,
                    ),
                ),
                (
                    "initiated_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("answered_at", models.DateTimeField(blank=True, null=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("duration_seconds", models.IntegerField(blank=True, null=True)),
                (
                    "end_reason",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("caller_hangup", "Caller Hangup"),
                            ("callee_hangup", "Callee Hangup"),
                            ("callee_declined", "Callee Declined"),
                            ("caller_cancelled", "Caller Cancelled"),
                            ("timeout", "Timeout"),
                            ("error", "Error"),
                        ],
                        max_length=30,
                        null=True,
                    ),
                ),
                (
                    "callee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incoming_calls",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "caller",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outgoing_calls",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "call_records",
                "ordering": ["-initiated_at"],
            },
        ),
        migrations.CreateModel(
            name="DeviceVoipToken",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "platform",
                    models.CharField(
                        choices=[("ios", "iOS"), ("android", "Android")],
                        max_length=10,
                    ),
                ),
                ("fcm_token", models.TextField(blank=True, null=True)),
                ("voip_token", models.TextField(blank=True, null=True)),
                ("device_id", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="voip_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "device_voip_tokens",
            },
        ),
        migrations.AddConstraint(
            model_name="devicevoiptoken",
            constraint=models.UniqueConstraint(
                fields=("user", "device_id"),
                name="unique_user_device",
            ),
        ),
    ]

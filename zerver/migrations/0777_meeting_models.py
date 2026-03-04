import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0776_realm_default_avatar_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="Meeting",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("topic", models.CharField(max_length=60)),
                ("deadline", models.DateTimeField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("proposed", "Proposed"),
                            ("deadline_passed", "Deadline Passed"),
                            ("confirmed", "Confirmed"),
                        ],
                        db_index=True,
                        default="proposed",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="owned_meetings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "stream",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="meetings",
                        to="zerver.stream",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="MeetingSlot",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("start_time", models.DateTimeField()),
                ("end_time", models.DateTimeField(blank=True, null=True)),
                (
                    "meeting",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="slots",
                        to="zerver.meeting",
                    ),
                ),
            ],
            options={
                "ordering": ["start_time"],
            },
        ),
        migrations.AddField(
            model_name="meeting",
            name="confirmed_slot",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="confirmed_for_meeting",
                to="zerver.meetingslot",
            ),
        ),
        migrations.CreateModel(
            name="MeetingResponse",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("available", models.BooleanField()),
                (
                    "slot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="responses",
                        to="zerver.meetingslot",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="meeting_responses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="meetingresponse",
            constraint=models.UniqueConstraint(
                fields=["slot", "user"], name="unique_meeting_response_per_slot_user"
            ),
        ),
        migrations.AddIndex(
            model_name="meeting",
            index=models.Index(fields=["stream", "status"], name="meeting_stream_status_idx"),
        ),
    ]

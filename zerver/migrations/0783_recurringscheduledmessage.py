import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0782_delete_unused_anonymous_groups"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecurringScheduledMessage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("content", models.TextField()),
                ("destinations", models.JSONField()),
                (
                    "recurrence_type",
                    models.CharField(
                        choices=[
                            ("one_time", "One time"),
                            ("daily", "Daily"),
                            ("weekly", "Weekly"),
                            ("specific_days", "Specific days"),
                        ],
                        default="one_time",
                        max_length=20,
                    ),
                ),
                ("recurrence_days", models.JSONField(default=list)),
                ("scheduled_time", models.TimeField()),
                ("next_delivery", models.DateTimeField(db_index=True)),
                ("is_active", models.BooleanField(default=True)),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="zerver.realm"
                    ),
                ),
                (
                    "sender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["next_delivery"],
                        name="zerver_active_recurring_by_time",
                        condition=models.Q(is_active=True),
                    )
                ],
            },
        ),
    ]

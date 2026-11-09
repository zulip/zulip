import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("zerver", "0815_merge")]

    operations = [
        migrations.CreateModel(
            name="MentionNotification",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="zerver.message"
                    ),
                ),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="zerver.userprofile"
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("message", "recipient"), name="unique_mention_notification"
                    )
                ],
            },
        ),
    ]

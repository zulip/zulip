from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0094_realm_filter_url_validator"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="usermessage",
            index=models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andz=1),
                name="zerver_usermessage_unread_message_id",
            ),
        ),
    ]

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0098_index_has_alert_word_user_messages"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="usermessage",
            index=models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=8) | Q(flags__andnz=16),
                name="zerver_usermessage_wildcard_mentioned_message_id",
            ),
        ),
    ]

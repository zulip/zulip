from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0097_reactions_emoji_code"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="usermessage",
            index=models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=512),
                name="zerver_usermessage_has_alert_word_message_id",
            ),
        ),
    ]

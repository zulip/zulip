from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0082_index_starred_user_messages"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="usermessage",
            index=models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=8),
                name="zerver_usermessage_mentioned_message_id",
            ),
        ),
    ]

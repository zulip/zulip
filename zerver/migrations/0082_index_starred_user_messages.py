from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0081_make_emoji_lowercase"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="usermessage",
            index=models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=2),
                name="zerver_usermessage_starred_message_id",
            ),
        ),
    ]

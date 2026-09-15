from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0807_usertopic_zerver_usertopic_user_visibility_recipient_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="alertword",
            name="automatically_follow_topics",
            field=models.BooleanField(db_default=False, default=False),
        ),
    ]

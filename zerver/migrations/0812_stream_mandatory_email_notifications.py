from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0811_usermessage_add_hide_link_previews"),
    ]

    operations = [
        migrations.AddField(
            model_name="stream",
            name="mandatory_email_notifications",
            field=models.BooleanField(default=False, db_default=False),
        ),
    ]

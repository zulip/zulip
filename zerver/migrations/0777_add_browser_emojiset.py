# Generated migration for adding browser emojiset option

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0776_realm_default_avatar_source"),
    ]

    operations = [
        migrations.AlterField(
            model_name="realmuserdefault",
            name="emojiset",
            field=models.CharField(
                choices=[
                    ("google", "Google"),
                    ("twitter", "Twitter"),
                    ("text", "Plain text"),
                    ("browser", "Browser default"),
                ],
                default="google",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="emojiset",
            field=models.CharField(
                choices=[
                    ("google", "Google"),
                    ("twitter", "Twitter"),
                    ("text", "Plain text"),
                    ("browser", "Browser default"),
                ],
                default="google",
                max_length=20,
            ),
        ),
    ]

# Generated manually to restore avatar_source default to 'D'
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0761_realm_default_newuser_avatar_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="avatar_source",
            field=models.CharField(
                default="D",
                choices=[
                    ("D", "Default (organization setting)"),
                    ("G", "Hosted by Gravatar"),
                    ("U", "Uploaded by user"),
                ],
                max_length=1,
            ),
        ),
    ]

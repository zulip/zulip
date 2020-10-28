from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0324_fix_deletion_cascade_behavior"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="webex_token",
            field=models.JSONField(default=None, null=True),
        ),
    ]

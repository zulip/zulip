from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0805_fix_deleteduser_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="stream",
            name="default_push_notifications",
            field=models.BooleanField(default=False, db_default=False),
        ),
    ]

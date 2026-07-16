from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0805_fix_deleteduser_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="stream",
            name="default_code_block_language",
            field=models.TextField(default="", db_default=""),
        ),
    ]

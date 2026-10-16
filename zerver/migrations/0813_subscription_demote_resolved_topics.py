from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0812_delete_inaccessible_user_topics"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="demote_resolved_topics",
            field=models.BooleanField(default=False, db_default=False),
        ),
    ]

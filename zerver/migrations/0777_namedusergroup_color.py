from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0776_realm_default_avatar_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="namedusergroup",
            name="color",
            field=models.CharField(db_default="", default="", max_length=10),
        ),
        migrations.AddField(
            model_name="namedusergroup",
            name="color_priority",
            field=models.PositiveIntegerField(default=None, null=True),
        ),
    ]

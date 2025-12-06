# Generated migration for adding color field to NamedUserGroup

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0761_realm_send_channel_events_messages"),
    ]

    operations = [
        migrations.AddField(
            model_name="namedusergroup",
            name="color",
            field=models.CharField(db_column="color", default="", max_length=7),
        ),
    ]

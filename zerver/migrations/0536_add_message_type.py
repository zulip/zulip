# Generated by Django 5.0.6 on 2024-06-05 17:51

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0535_remove_realm_create_public_stream_policy"),
    ]

    operations = [
        migrations.AddField(
            model_name="archivedmessage",
            name="type",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "Normal"), (2, "Resolve Topic Notification")], db_default=1, default=1
            ),
        ),
        migrations.AddField(
            model_name="message",
            name="type",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "Normal"), (2, "Resolve Topic Notification")], db_default=1, default=1
            ),
        ),
    ]

# Generated by Django 3.1.8 on 2021-04-27 22:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0320_realm_move_messages_between_streams_policy"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="enable_marketing_emails",
            field=models.BooleanField(default=True),
        ),
    ]

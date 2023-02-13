# Generated by Django 3.2.8 on 2021-10-21 07:23

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0425_realm_move_messages_between_streams_limit_seconds"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmuserdefault",
            name="email_address_visibility",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="email_address_visibility",
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]

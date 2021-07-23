# Generated by Django 3.2.5 on 2021-07-23 21:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0339_remove_realm_add_emoji_by_admins_only"),
    ]

    operations = [
        migrations.AddField(
            model_name="archivedmessage",
            name="type",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "Normal"),
                ],
                default=1,
            ),
        ),
        migrations.AddField(
            model_name="message",
            name="type",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "Normal"),
                ],
                default=1,
            ),
        ),
    ]

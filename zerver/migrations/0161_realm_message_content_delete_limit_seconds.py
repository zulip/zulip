# Generated by Django 1.11.11 on 2018-04-24 22:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0160_add_choice_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="message_content_delete_limit_seconds",
            field=models.IntegerField(default=600),
        ),
    ]

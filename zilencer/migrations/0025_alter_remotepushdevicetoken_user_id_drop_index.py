# Generated by Django 3.2.12 on 2022-03-10 12:34

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zilencer", "0024_remotepushdevicetoken_user_uuid"),
    ]

    operations = [
        migrations.AlterField(
            model_name="remotepushdevicetoken",
            name="user_id",
            field=models.BigIntegerField(null=True),
        ),
    ]

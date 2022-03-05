# Generated by Django 3.2.12 on 2022-03-05 15:03

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0380_userprofile_uuid_backfill"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4, unique=True),
        ),
    ]

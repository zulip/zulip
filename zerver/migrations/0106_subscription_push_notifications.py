# Generated by Django 1.11.4 on 2017-09-08 17:52
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0105_userprofile_enable_stream_push_notifications'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='push_notifications',
            field=models.BooleanField(default=False),
        ),
    ]

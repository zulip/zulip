# Generated by Django 1.11.4 on 2017-08-31 00:13
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0102_convert_muted_topic'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userprofile',
            name='muted_topics',
        ),
    ]

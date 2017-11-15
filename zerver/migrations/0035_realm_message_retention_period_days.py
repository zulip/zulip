# -*- coding: utf-8 -*-

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0034_userprofile_enable_online_push_notifications'),
    ]

    operations = [
        migrations.AddField(
            model_name='realm',
            name='message_retention_days',
            field=models.IntegerField(null=True),
        ),
    ]

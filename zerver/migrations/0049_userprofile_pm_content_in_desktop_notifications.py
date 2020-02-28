# -*- coding: utf-8 -*-

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0048_enter_sends_default_to_false'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='pm_content_in_desktop_notifications',
            field=models.BooleanField(default=True),
        ),
    ]

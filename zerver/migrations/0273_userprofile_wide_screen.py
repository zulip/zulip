# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0272_realm_default_code_block_language'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='wide_screen',
            field=models.BooleanField(default=False),
        ),
    ]

# -*- coding: utf-8 -*-

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0035_realm_message_retention_period_days'),
    ]

    operations = [
        migrations.RenameField(
            model_name='realm',
            old_name='subdomain',
            new_name='string_id',
        ),
    ]

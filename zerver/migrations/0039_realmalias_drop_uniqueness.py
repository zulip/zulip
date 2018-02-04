# -*- coding: utf-8 -*-

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0038_realm_change_to_community_defaults'),
    ]

    operations = [
        migrations.AlterField(
            model_name='realmalias',
            name='domain',
            field=models.CharField(max_length=80, db_index=True),
        ),
    ]

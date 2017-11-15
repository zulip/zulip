# -*- coding: utf-8 -*-

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0030_realm_org_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='avatar_source',
            field=models.CharField(choices=[('G', 'Hosted by Gravatar'), ('U', 'Uploaded by user')], max_length=1, default='G'),
        ),
    ]

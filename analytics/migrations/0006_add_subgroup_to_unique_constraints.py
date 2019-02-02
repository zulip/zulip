# -*- coding: utf-8 -*-
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0005_alter_field_size'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='installationcount',
            unique_together=set([('property', 'subgroup', 'end_time', 'interval')]),
        ),
        migrations.AlterUniqueTogether(
            name='realmcount',
            unique_together=set([('realm', 'property', 'subgroup', 'end_time', 'interval')]),
        ),
        migrations.AlterUniqueTogether(
            name='streamcount',
            unique_together=set([('stream', 'property', 'subgroup', 'end_time', 'interval')]),
        ),
        migrations.AlterUniqueTogether(
            name='usercount',
            unique_together=set([('user', 'property', 'subgroup', 'end_time', 'interval')]),
        ),
    ]

# -*- coding: utf-8 -*-
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='huddlecount',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='huddlecount',
            name='anomaly',
        ),
        migrations.RemoveField(
            model_name='huddlecount',
            name='huddle',
        ),
        migrations.RemoveField(
            model_name='huddlecount',
            name='user',
        ),
        migrations.DeleteModel(
            name='HuddleCount',
        ),
    ]

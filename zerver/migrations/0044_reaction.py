# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import zerver.lib.str_utils


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0043_realm_filter_validators'),
    ]

    operations = [
        migrations.CreateModel(
            name='Reaction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('user_profile', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('message', models.ForeignKey(to='zerver.Message')),
                ('emoji_name', models.TextField()),
            ],
            bases=(zerver.lib.str_utils.ModelReprMixin, models.Model),
        ),
        migrations.AlterUniqueTogether(
            name='reaction',
            unique_together=set([('user_profile', 'message', 'emoji_name')]),
        ),
    ]

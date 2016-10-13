# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0012_remove_appledevicetoken'),
    ]

    operations = [
        migrations.AlterField(
            model_name='realmemoji',
            name='img_url',
            field=models.URLField(),
        ),
        migrations.AlterField(
            model_name='realmemoji',
            name='name',
            field=models.TextField(validators=[django.core.validators.MinLengthValidator(1), django.core.validators.RegexValidator(regex='^[0-9a-zA-Z.\\-_]+(?<![.\\-_])$')]),
        ),
    ]

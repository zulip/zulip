# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators
import zerver.models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0042_attachment_file_name_length'),
    ]

    operations = [
        migrations.AlterField(
            model_name='realmfilter',
            name='pattern',
            field=models.TextField(validators=[zerver.models.filter_pattern_validator]),
        ),
        migrations.AlterField(
            model_name='realmfilter',
            name='url_format_string',
            field=models.TextField(validators=[django.core.validators.URLValidator, zerver.models.filter_format_validator]),
        ),
    ]

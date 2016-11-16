# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0042_attachment_file_name_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='realm',
            name='default_domain',
            field=models.CharField(default=b'mit.edu', max_length=40, editable=False, db_index=True),
        ),
    ]

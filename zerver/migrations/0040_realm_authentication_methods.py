# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import bitfield.models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0039_realmalias_drop_uniqueness'),
    ]

    operations = [
        migrations.AddField(
            model_name='realm',
            name='authentication_methods',
            field=bitfield.models.BitField(['Google', 'Email', 'GitHub', 'LDAP', 'Dev', 'RemoteUser'], default=2147483647),
        ),
    ]

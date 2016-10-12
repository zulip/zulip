# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0005_auto_20150920_1340'),
    ]

    operations = [
        migrations.RunSQL("CREATE INDEX upper_userprofile_email_idx ON zerver_userprofile ((upper(email)));",
                          reverse_sql="DROP INDEX upper_userprofile_email_idx;"),
    ]

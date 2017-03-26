# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0002_django_1_8'),
    ]

    operations = [
        migrations.RunSQL("CREATE INDEX upper_subject_idx ON zerver_message ((upper(subject)));",
                          reverse_sql="DROP INDEX upper_subject_idx;"),
        migrations.RunSQL("CREATE INDEX upper_stream_name_idx ON zerver_stream ((upper(name)));",
                          reverse_sql="DROP INDEX upper_stream_name_idx;")
    ]

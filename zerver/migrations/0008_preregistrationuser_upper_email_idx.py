# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0007_userprofile_is_bot_active_indexes'),
    ]

    operations = [
        migrations.RunSQL("CREATE INDEX upper_preregistration_email_idx ON zerver_preregistrationuser ((upper(email)));",
                          reverse_sql="DROP INDEX upper_preregistration_email_idx;"),
    ]

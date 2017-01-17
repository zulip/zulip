# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0049_userprofile_pm_content_in_desktop_notifications'),
    ]

    operations = [
        migrations.RunSQL("""
ALTER TEXT SEARCH CONFIGURATION zulip.english_us_search
ALTER MAPPING FOR tag, entity
WITH english_us_hunspell, english_stem;
""")
    ]

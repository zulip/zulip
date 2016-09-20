# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

from zerver.lib.upload import upload_backend


def verify_medium_avatar_image(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    user_profile_model = apps.get_model('zerver', 'UserProfile')
    for user_profile in user_profile_model.objects.filter(avatar_source=u"U"):
        upload_backend.ensure_medium_avatar_image(user_profile.email)


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0031_remove_system_avatar_source'),
    ]

    operations = [
        migrations.RunPython(verify_medium_avatar_image)
    ]

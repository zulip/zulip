# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

def set_subdomain_of_default_realm(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    if settings.DEVELOPMENT:
        Realm = apps.get_model('zerver', 'Realm')
        try:
            default_realm = Realm.objects.get(domain="zulip.com")
        except ObjectDoesNotExist:
            default_realm = None

        if default_realm is not None:
            default_realm.subdomain = "zulip"
            default_realm.save()

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0028_userprofile_tos_version'),
    ]

    operations = [
        migrations.AddField(
            model_name='realm',
            name='subdomain',
            field=models.CharField(max_length=40, unique=True, null=True),
        ),
        migrations.RunPython(set_subdomain_of_default_realm)
    ]

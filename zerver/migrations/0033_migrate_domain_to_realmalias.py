# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

def add_domain_to_realm_alias_if_needed(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    Realm = apps.get_model('zerver', 'Realm')
    RealmAlias = apps.get_model('zerver', 'RealmAlias')

    for realm in Realm.objects.all():
        # if realm.domain already exists in RealmAlias, assume it is correct
        if not RealmAlias.objects.filter(domain=realm.domain).exists():
            if realm.domain[-8:] != 'acme.com':
                RealmAlias.objects.create(realm=realm, domain=realm.domain)

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0032_verify_all_medium_avatar_images'),
    ]

    operations = [
        migrations.RunPython(add_domain_to_realm_alias_if_needed)
    ]

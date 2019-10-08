# -*- coding: utf-8 -*-
from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

def clear_analytics_tables(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    UserCount = apps.get_model('analytics', 'UserCount')
    StreamCount = apps.get_model('analytics', 'StreamCount')
    RealmCount = apps.get_model('analytics', 'RealmCount')
    InstallationCount = apps.get_model('analytics', 'InstallationCount')
    FillState = apps.get_model('analytics', 'FillState')

    UserCount.objects.all().delete()
    StreamCount.objects.all().delete()
    RealmCount.objects.all().delete()
    InstallationCount.objects.all().delete()
    FillState.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0010_clear_messages_sent_values'),
    ]

    operations = [
        migrations.RunPython(clear_analytics_tables),
    ]

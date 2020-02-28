# -*- coding: utf-8 -*-
from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

def set_tutorial_status_to_finished(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    UserProfile = apps.get_model('zerver', 'UserProfile')
    UserProfile.objects.update(tutorial_status='F')

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0108_fix_default_string_id'),
    ]

    operations = [
        migrations.RunPython(set_tutorial_status_to_finished)
    ]

# -*- coding: utf-8 -*-
from django.db import models, migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from typing import Text

def remove_special_chars_from_streamname(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    Stream = apps.get_model('zerver', 'Stream')
    NAME_INVALID_CHARS = ['*', '@', '`', '#']
    for stream in Stream.objects.all():
        if (set(stream.name).intersection(NAME_INVALID_CHARS)):
            for char in NAME_INVALID_CHARS:
                stream.name = stream.name.replace(char, ' ').strip()

            while Stream.objects.filter(name__iexact=stream.name, realm=stream.realm).exists():
                stream.name = stream.name + '^'
                if len(stream.name) > 60:
                    # extremely unlikely, so just do something valid
                    stream.name = stream.name[-60:]
            stream.save(update_fields=['name'])

def remove_special_chars_from_username(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    UserProfile = apps.get_model('zerver', 'UserProfile')
    NAME_INVALID_CHARS = ['*', '`', '>', '"', '@', '#']
    for userprofile in UserProfile.objects.all():
        if (set(userprofile.full_name).intersection(NAME_INVALID_CHARS)):
            for char in NAME_INVALID_CHARS:
                userprofile.full_name = userprofile.full_name.replace(char, ' ').strip()
            userprofile.save(update_fields=['full_name'])

        if (set(userprofile.short_name).intersection(NAME_INVALID_CHARS)):
            for char in NAME_INVALID_CHARS:
                userprofile.short_name = userprofile.short_name.replace(char, ' ').strip()
            userprofile.save(update_fields=['short_name'])

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0126_prereg_remove_users_without_realm'),
    ]

    operations = [
        migrations.RunPython(remove_special_chars_from_streamname),
        migrations.RunPython(remove_special_chars_from_username),
    ]

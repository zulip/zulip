# -*- coding: utf-8 -*-

from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

def move_to_seperate_table(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    UserProfile = apps.get_model('zerver', 'UserProfile')
    AlertWords = apps.get_model('zerver', 'AlertWords')

    for user_profile in UserProfile.objects.all():

        list_of_words = user_profile.alert_words
        if list_of_words != "[]":
            list_of_words = list_of_words[2:-2]
            list_of_words = list_of_words.split('\",\"')
            for word in list_of_words:
                AlertWords.objects.create(user_profile=user_profile, word=word)


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0261_alertwords'),
    ]

    operations = [
        migrations.RunPython(move_to_seperate_table)
    ]

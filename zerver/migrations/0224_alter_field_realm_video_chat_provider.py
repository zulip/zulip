# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-05-09 06:54
from __future__ import unicode_literals

from django.db import migrations, models
from typing import Dict, Any, Optional
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

def get_video_chat_provider_detail(providers_dict: Dict[str, Dict[str, Any]],
                                   p_name: Optional[str]=None, p_id: Optional[int]=None
                                   ) -> Dict[str, Any]:
    for provider in providers_dict.values():
        if (p_name and provider['name'] == p_name):
            return provider
        if (p_id and provider['id'] == p_id):
            return provider
    return dict()

def update_existing_video_chat_provider_values(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    Realm = apps.get_model('zerver', 'Realm')

    for realm in Realm.objects.all():
        realm.video_chat_provider = get_video_chat_provider_detail(Realm.VIDEO_CHAT_PROVIDER,
                                                                   p_name=realm.video_chat_provider)['id']
        realm.save(update_fields=["video_chat_provider"])

def reverse_code(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    Realm = apps.get_model("zerver", "Realm")

    for realm in Realm.objects.all():
        realm.video_chat_provider = get_video_chat_provider_detail(Realm.VIDEO_CHAT_PROVIDER,
                                                                   p_id=realm.video_chat_provider)['name']
        realm.save(update_fields=["video_chat_provider"])

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0223_rename_to_is_muted'),
    ]

    operations = [
        migrations.AlterField(
            model_name='realm',
            name='video_chat_provider',
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.RunPython(update_existing_video_chat_provider_values,
                             reverse_code=reverse_code),
    ]

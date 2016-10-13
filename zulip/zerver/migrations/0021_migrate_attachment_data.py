# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.conf import settings

from zerver.models import Recipient

def migrate_existing_data(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    Attachment = apps.get_model('zerver', 'Attachment')
    Stream = apps.get_model('zerver', 'Stream')

    attachments = Attachment.objects.all()
    for entry in attachments:
        owner = entry.owner
        entry.realm = owner.realm
        for message in entry.messages.all():
            if owner == message.sender:
                if message.recipient.type == Recipient.STREAM:
                    stream = Stream.objects.get(id=message.recipient.type_id)
                    is_realm_public = stream.realm.domain != "mit.edu" and not stream.invite_only
                    entry.is_realm_public = entry.is_realm_public or is_realm_public

        entry.save()

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0020_add_tracking_attachment'),
    ]

    operations = [
        migrations.RunPython(migrate_existing_data)
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import glob

from django.db import models, migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.conf import settings

from boto.s3.connection import S3Connection

from zerver.models import Recipient
from zerver.lib.upload import get_bucket

def get_all_local_path_ids():
    base_path = os.path.join(settings.LOCAL_UPLOADS_DIR, 'files')
    paths = glob.glob(base_path + '/*/*/*/*')
    path_ids = [path.replace(base_path + '/', '') for path in paths]
    return path_ids

def get_all_s3_path_ids():
    conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
    bucket_name = settings.S3_AUTH_UPLOADS_BUCKET
    bucket = get_bucket(conn, bucket_name)
    return [key.name for key in list(bucket.list())]

def get_all_path_ids():
    if settings.LOCAL_UPLOADS_DIR is not None:
        return get_all_local_path_ids()
    else:
        return get_all_s3_path_ids()

def migrate_existing_data(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    Attachment = apps.get_model('zerver', 'Attachment')
    Stream = apps.get_model('zerver', 'Stream')

    attachments = Attachment.objects.all()
    remaining_files = get_all_path_ids()
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
        remaining_files.remove(entry.path_id)

    for path_id in remaining_files:
        file_name = path_id.split('/')[-1]
        Attachment.objects.create(file_name=file_name, path_id=path_id, is_realm_public=True)

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0020_add_tracking_attachment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attachment',
            name='owner',
            field=models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True),
        ),
        migrations.RunPython(migrate_existing_data)
    ]

# -*- coding: utf-8 -*-

from typing import Text, Dict

from boto.s3.bucket import Bucket
from boto.s3.connection import S3Connection
from boto.s3.key import Key
from django.conf import settings
from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

import os
import urllib

def add_content_disposition_to_s3_uploads(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    if settings.LOCAL_UPLOADS_DIR is None:
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        bucket_name = settings.S3_AUTH_UPLOADS_BUCKET
        bucket = conn.get_bucket(bucket_name, validate=False)

        all_keys = map(lambda key: key.name, bucket.get_all_keys())
        for key_name in all_keys:
            key = bucket.get_key(key_name)
            content_type = key.content_type
            content_disposition = key.content_disposition

            if content_disposition is not None:
                continue

            attachment = True
            if content_type.startswith("image/") or content_type == "application/pdf":
                attachment = False

            headers = {}  # type: Dict[Text, Text]
            headers['Content-Type'] = content_type
            if attachment:
                parts = ["attachment"]
                quoted_filename = urllib.parse.quote(os.path.basename(key_name))
                parts.append("filename*=UTF-8''%s" % (quoted_filename))
                headers['Content-Disposition'] = '; '.join(parts)

            bucket.copy_key(key_name,
                            bucket_name,
                            key_name,
                            preserve_acl=True,
                            headers=headers)

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0155_change_default_realm_description'),
    ]

    operations = [
        migrations.RunPython(add_content_disposition_to_s3_uploads,
                             reverse_code=migrations.RunPython.noop)
    ]

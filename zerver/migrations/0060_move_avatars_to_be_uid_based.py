# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-27 17:03
from __future__ import unicode_literals

from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from zerver.lib.avatar_hash import user_avatar_hash, user_avatar_path
from boto.s3.bucket import Bucket
from boto.s3.key import Key
from boto.s3.connection import S3Connection
from typing import Text
import requests
import os


def mkdirs(path):
    # type: (Text) -> None
    dirname = os.path.dirname(path)
    if not os.path.isdir(dirname):
        os.makedirs(dirname)

def move_local_file(type, path_src, path_dst):
    # type: (Text, Text, Text) -> None
    src_file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, type, path_src)
    dst_file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, type, path_dst)
    mkdirs(dst_file_path)
    os.rename(src_file_path, dst_file_path)

def move_avatars_to_be_uid_based(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    user_profile_model = apps.get_model('zerver', 'UserProfile')
    if settings.LOCAL_UPLOADS_DIR is not None:
        for user_profile in user_profile_model.objects.filter(avatar_source=u"U"):
            src_file_name = user_avatar_hash(user_profile.email)
            dst_file_name = user_avatar_path(user_profile)
            move_local_file('avatars', src_file_name + '.original', dst_file_name + '.original')
            move_local_file('avatars', src_file_name + '-medium.png', dst_file_name + '-medium.png')
            move_local_file('avatars', src_file_name + '.png', dst_file_name + '.png')
    else:
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        bucket_name = settings.S3_AVATAR_BUCKET
        bucket = conn.get_bucket(bucket_name, validate=False)
        for user_profile in user_profile_model.objects.filter(avatar_source=u"U"):
            bucket.copy_key(user_avatar_path(user_profile) + ".original",
                            bucket,
                            user_avatar_hash(user_profile.email) + ".original")
            bucket.copy_key(user_avatar_path(user_profile) + "-medium.png",
                            bucket,
                            user_avatar_hash(user_profile.email) + "-medium.png")
            bucket.copy_key(user_avatar_path(user_profile),
                            bucket,
                            user_avatar_hash(user_profile.email))

        # From an error handling sanity perspective, it's best to
        # start deleting after everything is copied, so that recovery
        # from failures is easy (just rerun one loop or the other).
        for user_profile in user_profile_model.objects.filter(avatar_source=u"U"):
            bucket.delete_key(user_avatar_hash(user_profile.email) + ".original")
            bucket.delete_key(user_avatar_hash(user_profile.email) + "-medium.png")
            bucket.delete_key(user_avatar_hash(user_profile.email))

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0059_userprofile_quota'),
    ]

    operations = [
        migrations.RunPython(move_avatars_to_be_uid_based)
    ]

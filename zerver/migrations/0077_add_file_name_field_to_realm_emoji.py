# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-09 05:23
from __future__ import unicode_literals

import os
import io
import requests

from mimetypes import guess_type

from PIL import Image
from PIL import ImageOps
from django.db import migrations, models

from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.conf import settings
from boto.s3.key import Key
from boto.s3.connection import S3Connection
from requests import ConnectionError, Response
from typing import Dict, Text, Tuple, Optional, Union

from six import binary_type


def force_str(s, encoding='utf-8'):
    # type: (Union[Text, binary_type], Text) -> str
    """converts a string to a native string"""
    if isinstance(s, str):
        return s
    elif isinstance(s, Text):
        return s.encode(str(encoding))
    elif isinstance(s, binary_type):
        return s.decode(encoding)
    else:
        raise TypeError("force_str expects a string type")


class Uploader(object):
    def __init__(self):
        # type: () -> None
        self.path_template = "{realm_id}/emoji/{emoji_file_name}"
        self.emoji_size = (64, 64)

    def upload_files(self, response, resized_image, dst_path_id):
        # type: (Response, binary_type, Text) -> None
        raise NotImplementedError()

    def get_dst_path_id(self, realm_id, url, emoji_name):
        # type: (int, Text, Text) -> Tuple[Text,Text]
        _, image_ext = os.path.splitext(url)
        file_name = ''.join((emoji_name, image_ext))
        return file_name, self.path_template.format(realm_id=realm_id, emoji_file_name=file_name)

    def resize_emoji(self, image_data):
        # type: (binary_type) -> Optional[binary_type]
        im = Image.open(io.BytesIO(image_data))
        format_ = im.format
        if format_ == 'GIF' and im.is_animated:
            return None
        im = ImageOps.fit(im, self.emoji_size, Image.ANTIALIAS)
        out = io.BytesIO()
        im.save(out, format_)
        return out.getvalue()

    def upload_emoji(self, realm_id, image_url, emoji_name):
        # type: (int, Text, Text) -> Optional[Text]
        file_name, dst_path_id = self.get_dst_path_id(realm_id, image_url, emoji_name)
        try:
            response = requests.get(image_url, stream=True)
        except ConnectionError:
            return None
        if response.status_code != 200:
            return None
        try:
            resized_image = self.resize_emoji(response.content)
        except IOError:
            return None
        self.upload_files(response, resized_image, dst_path_id)
        return file_name


class LocalUploader(Uploader):
    def __init__(self):
        # type: () -> None
        super(LocalUploader, self).__init__()

    @staticmethod
    def mkdirs(path):
        # type: (Text) -> None
        dirname = os.path.dirname(path)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)

    def write_local_file(self, path, file_data):
        # type: (Text, binary_type) -> None
        self.mkdirs(path)
        with open(path, 'wb') as f:   # type: ignore
            f.write(file_data)

    def upload_files(self, response, resized_image, dst_path_id):
        # type: (Response, binary_type, Text) -> None
        dst_file = os.path.join(settings.LOCAL_UPLOADS_DIR, 'avatars', dst_path_id)
        if resized_image:
            self.write_local_file(dst_file, resized_image)
        else:
            self.write_local_file(dst_file, response.content)
        self.write_local_file('.'.join((dst_file, 'original')), response.content)


class S3Uploader(Uploader):
    def __init__(self):
        # type: () -> None
        super(S3Uploader, self).__init__()
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        bucket_name = settings.S3_AVATAR_BUCKET
        self.bucket = conn.get_bucket(bucket_name, validate=False)

    def upload_to_s3(self, path, file_data, headers):
        # type: (Text, binary_type, Optional[Dict[Text, Text]]) -> None
        key = Key(self.bucket)
        key.key = path
        key.set_contents_from_string(force_str(file_data), headers=headers)

    def upload_files(self, response, resized_image, dst_path_id):
        # type: (Response, binary_type, Text) -> None
        headers = None  # type: Optional[Dict[Text, Text]]
        content_type = response.headers.get(str("Content-Type")) or guess_type(dst_path_id)[0]
        if content_type:
            headers = {u'Content-Type': content_type}
        if resized_image:
            self.upload_to_s3(dst_path_id, resized_image, headers)
        else:
            self.upload_to_s3(dst_path_id, response.content, headers)
        self.upload_to_s3('.'.join((dst_path_id, 'original')), response.content, headers)

def get_uploader():
    # type: () -> Uploader
    if settings.LOCAL_UPLOADS_DIR is None:
        return S3Uploader()
    return LocalUploader()


def upload_emoji_to_storage(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    realm_emoji_model = apps.get_model('zerver', 'RealmEmoji')
    uploader = get_uploader()  # type: Uploader
    for emoji in realm_emoji_model.objects.all():
        file_name = uploader.upload_emoji(emoji.realm_id, emoji.img_url, emoji.name)
        emoji.file_name = file_name
        emoji.save()


class Migration(migrations.Migration):
    dependencies = [
        ('zerver', '0076_userprofile_emojiset'),
    ]

    operations = [
        migrations.AddField(
            model_name='realmemoji',
            name='file_name',
            field=models.TextField(db_index=True, null=True),
        ),
        migrations.RunPython(upload_emoji_to_storage),
        migrations.RemoveField(
            model_name='realmemoji',
            name='img_url',
        ),
    ]

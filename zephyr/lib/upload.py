from __future__ import absolute_import

from django.conf import settings
from django.template.defaultfilters import slugify

from zephyr.lib.avatar import user_avatar_hash

from boto.s3.key import Key
from boto.s3.connection import S3Connection
from mimetypes import guess_type, guess_extension

import base64
import os

# Performance Note:
#
# For writing files to S3, the file could either be stored in RAM
# (if it is less than 2.5MiB or so) or an actual temporary file on disk.
#
# Because we set FILE_UPLOAD_MAX_MEMORY_SIZE to 0, only the latter case
# should occur in practice.
#
# This is great, because passing the pseudofile object that Django gives
# you to boto would be a pain.

def gen_s3_key(user_profile, name):
    split_name = name.split('.')
    base = ".".join(split_name[:-1])
    extension = split_name[-1]

    # To come up with a s3 key we randomly generate a "directory". The "file
    # name" is the original filename provided by the user run through Django's
    # slugify.

    return base64.urlsafe_b64encode(os.urandom(60)) + "/" + slugify(base) + "." + slugify(extension)

def upload_image_to_s3(
        bucket_name,
        file_name,
        content_type,
        user_profile_id,
        user_file,
    ):

    conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
    key = Key(conn.get_bucket(bucket_name))
    key.key = file_name
    key.set_metadata("user_profile_id", str(user_profile_id))

    if content_type:
        headers = {'Content-Type': content_type}
    else:
        headers = None

    key.set_contents_from_filename(
            user_file.temporary_file_path(),
            headers=headers)

def get_file_info(request, user_file):
    uploaded_file_name = user_file.name
    content_type = request.GET.get('mimetype')
    if content_type is None:
        content_type = guess_type(uploaded_file_name)[0]
    else:
        uploaded_file_name = uploaded_file_name + guess_extension(content_type)
    return uploaded_file_name, content_type


def upload_message_image(request, user_file, user_profile):
    uploaded_file_name, content_type = get_file_info(request, user_file)
    bucket_name = settings.S3_BUCKET
    s3_file_name = gen_s3_key(user_profile, uploaded_file_name)
    upload_image_to_s3(
            bucket_name,
            s3_file_name,
            content_type,
            user_profile.id,
            user_file,
    )
    return "https://%s.s3.amazonaws.com/%s" % (bucket_name, s3_file_name)

def upload_avatar_image(user_file, user_profile, email):
    content_type = guess_type(user_file.name)[0]
    bucket_name = settings.S3_AVATAR_BUCKET
    s3_file_name = user_avatar_hash(email)
    upload_image_to_s3(
        bucket_name,
        s3_file_name,
        content_type,
        user_profile.id,
        user_file,
    )
    # See avatar_url in avatar.py for URL.  (That code also handles the case
    # that users use gravatar.)

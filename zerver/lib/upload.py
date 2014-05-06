from __future__ import absolute_import

from django.conf import settings
from django.template.defaultfilters import slugify

from zerver.lib.avatar import user_avatar_hash

from boto.s3.key import Key
from boto.s3.connection import S3Connection
from mimetypes import guess_type, guess_extension

from zerver.models import get_user_profile_by_id

import base64
import os
from PIL import Image, ImageOps
from StringIO import StringIO
import random

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

# To come up with a s3 key we randomly generate a "directory". The "file
# name" is the original filename provided by the user run through Django's
# slugify.

def sanitize_name(name):
    split_name = name.split('.')
    base = ".".join(split_name[:-1])
    extension = split_name[-1]
    return slugify(base) + "." + slugify(extension)

def random_name(bytes=60):
    return base64.urlsafe_b64encode(os.urandom(bytes))

def resize_avatar(image_data):
    AVATAR_SIZE = 100
    im = Image.open(StringIO(image_data))
    im = ImageOps.fit(im, (AVATAR_SIZE, AVATAR_SIZE), Image.ANTIALIAS)
    out = StringIO()
    im.save(out, format='png')
    return out.getvalue()


### S3

def get_bucket(conn, bucket_name):
    # Calling get_bucket() with validate=True can apparently lead
    # to expensive S3 bills:
    #    http://www.appneta.com/blog/s3-list-get-bucket-default/
    # The benefits of validation aren't completely clear to us, and
    # we want to save on our bills, so we set the validate flag to False.
    # (We think setting validate to True would cause us to fail faster
    #  in situations where buckets don't exist, but that shouldn't be
    #  an issue for us.)
    bucket = conn.get_bucket(bucket_name, validate=False)
    return bucket

def upload_image_to_s3(
        bucket_name,
        file_name,
        content_type,
        user_profile,
        contents,
    ):

    conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
    bucket = get_bucket(conn, bucket_name)
    key = Key(bucket)
    key.key = file_name
    key.set_metadata("user_profile_id", str(user_profile.id))
    key.set_metadata("realm_id", str(user_profile.realm.id))

    if content_type:
        headers = {'Content-Type': content_type}
    else:
        headers = None

    key.set_contents_from_string(contents, headers=headers)

def get_file_info(request, user_file):
    uploaded_file_name = user_file.name
    content_type = request.GET.get('mimetype')
    if content_type is None:
        content_type = guess_type(uploaded_file_name)[0]
    else:
        uploaded_file_name = uploaded_file_name + guess_extension(content_type)
    return uploaded_file_name, content_type

def upload_message_image_s3(uploaded_file_name, content_type, file_data, user_profile, target_realm=None):
    bucket_name = settings.S3_AUTH_UPLOADS_BUCKET
    s3_file_name = "/".join([
        str(target_realm.id if target_realm is not None else user_profile.realm.id),
        random_name(18),
        sanitize_name(uploaded_file_name)
    ])
    url = "/user_uploads/%s" % (s3_file_name)

    upload_image_to_s3(
            bucket_name,
            s3_file_name,
            content_type,
            user_profile,
            file_data
    )
    return url

def get_signed_upload_url(path):
    conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
    return conn.generate_url(15, 'GET', bucket=settings.S3_AUTH_UPLOADS_BUCKET, key=path)

def get_realm_for_filename(path):
    conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
    key = get_bucket(conn, settings.S3_AUTH_UPLOADS_BUCKET).get_key(path)
    if key is None:
        # This happens if the key does not exist.
        return None
    return get_user_profile_by_id(key.metadata["user_profile_id"]).realm.id

def upload_avatar_image_s3(user_file, user_profile, email):
    content_type = guess_type(user_file.name)[0]
    bucket_name = settings.S3_AVATAR_BUCKET
    s3_file_name = user_avatar_hash(email)

    image_data = user_file.read()
    upload_image_to_s3(
        bucket_name,
        s3_file_name + ".original",
        content_type,
        user_profile,
        image_data,
    )

    resized_data = resize_avatar(image_data)
    upload_image_to_s3(
        bucket_name,
        s3_file_name,
        'image/png',
        user_profile,
        resized_data,
    )
    # See avatar_url in avatar.py for URL.  (That code also handles the case
    # that users use gravatar.)

### Local

def mkdirs(path):
    dirname = os.path.dirname(path)
    if not os.path.isdir(dirname):
        os.makedirs(dirname)

def write_local_file(type, path, file_data):
    file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, type, path)
    mkdirs(file_path)
    with open(file_path, 'wb') as f:
        f.write(file_data)

def upload_message_image_local(uploaded_file_name, content_type, file_data, user_profile, target_realm=None):
    # Split into 256 subdirectories to prevent directories from getting too big
    path = "/".join([
        str(user_profile.realm.id),
        format(random.randint(0, 255), 'x'),
        random_name(18),
        sanitize_name(uploaded_file_name)
    ])

    write_local_file('files', path, file_data)

    return '/user_uploads/' + path

def upload_avatar_image_local(user_file, user_profile, email):
    email_hash = user_avatar_hash(email)

    image_data = user_file.read()
    write_local_file('avatars', email_hash+'.original', image_data)

    resized_data = resize_avatar(image_data)
    write_local_file('avatars', email_hash+'.png', resized_data)

### Common

if settings.LOCAL_UPLOADS_DIR is not None:
    upload_message_image = upload_message_image_local
    upload_avatar_image  = upload_avatar_image_local
else:
    upload_message_image = upload_message_image_s3
    upload_avatar_image  = upload_avatar_image_s3

def upload_message_image_through_web_client(request, user_file, user_profile):
    uploaded_file_name, content_type = get_file_info(request, user_file)
    return upload_message_image(uploaded_file_name, content_type, user_file.read(), user_profile)

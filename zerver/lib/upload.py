from typing import Dict, Optional, Tuple

from django.utils.translation import ugettext as _
from django.conf import settings
from django.core.files import File
from django.http import HttpRequest
from jinja2 import Markup as mark_safe
import unicodedata

from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.exceptions import JsonableError, ErrorCode

from boto.s3.bucket import Bucket
from boto.s3.key import Key
from boto.s3.connection import S3Connection
from mimetypes import guess_type, guess_extension

from zerver.models import get_user_profile_by_id
from zerver.models import Attachment
from zerver.models import Realm, RealmEmoji, UserProfile, Message

import urllib
import base64
import os
import re
from PIL import Image, ImageOps, ExifTags
from PIL.Image import DecompressionBombError
from PIL.GifImagePlugin import GifImageFile
import io
import random
import logging

DEFAULT_AVATAR_SIZE = 100
MEDIUM_AVATAR_SIZE = 500
DEFAULT_EMOJI_SIZE = 64

# These sizes were selected based on looking at the maximum common
# sizes in a library of animated custom emoji, balanced against the
# network cost of very large emoji images.
MAX_EMOJI_GIF_SIZE = 128
MAX_EMOJI_GIF_FILE_SIZE_BYTES = 128 * 1024 * 1024  # 128 kb

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

# To come up with a s3 key we randomly generate a "directory". The
# "file name" is the original filename provided by the user run
# through a sanitization function.

class RealmUploadQuotaError(JsonableError):
    code = ErrorCode.REALM_UPLOAD_QUOTA

attachment_url_re = re.compile(r'[/\-]user[\-_]uploads[/\.-].*?(?=[ )]|\Z)')

def attachment_url_to_path_id(attachment_url: str) -> str:
    path_id_raw = re.sub(r'[/\-]user[\-_]uploads[/\.-]', '', attachment_url)
    # Remove any extra '.' after file extension. These are probably added by the user
    return re.sub('[.]+$', '', path_id_raw, re.M)

def sanitize_name(value: str) -> str:
    """
    Sanitizes a value to be safe to store in a Linux filesystem, in
    S3, and in a URL.  So unicode is allowed, but not special
    characters other than ".", "-", and "_".

    This implementation is based on django.utils.text.slugify; it is
    modified by:
    * adding '.' and '_' to the list of allowed characters.
    * preserving the case of the value.
    """
    value = unicodedata.normalize('NFKC', value)
    value = re.sub(r'[^\w\s._-]', '', value, flags=re.U).strip()
    return mark_safe(re.sub(r'[-\s]+', '-', value, flags=re.U))

def random_name(bytes: int=60) -> str:
    return base64.urlsafe_b64encode(os.urandom(bytes)).decode('utf-8')

class BadImageError(JsonableError):
    code = ErrorCode.BAD_IMAGE

name_to_tag_num = dict((name, num) for num, name in ExifTags.TAGS.items())

# https://stackoverflow.com/a/6218425
def exif_rotate(image: Image) -> Image:
    if not hasattr(image, '_getexif'):
        return image
    exif_data = image._getexif()
    if exif_data is None:
        return image

    exif_dict = dict(exif_data.items())
    orientation = exif_dict.get(name_to_tag_num['Orientation'])

    if orientation == 3:
        return image.rotate(180, expand=True)
    elif orientation == 6:
        return image.rotate(270, expand=True)
    elif orientation == 8:
        return image.rotate(90, expand=True)

    return image

def resize_avatar(image_data: bytes, size: int=DEFAULT_AVATAR_SIZE) -> bytes:
    try:
        im = Image.open(io.BytesIO(image_data))
        im = exif_rotate(im)
        im = ImageOps.fit(im, (size, size), Image.ANTIALIAS)
    except IOError:
        raise BadImageError(_("Could not decode image; did you upload an image file?"))
    except DecompressionBombError:
        raise BadImageError(_("Image size exceeds limit."))
    out = io.BytesIO()
    if im.mode == 'CMYK':
        im = im.convert('RGB')
    im.save(out, format='png')
    return out.getvalue()

def resize_logo(image_data: bytes) -> bytes:
    try:
        im = Image.open(io.BytesIO(image_data))
        im = exif_rotate(im)
        im.thumbnail((8*DEFAULT_AVATAR_SIZE, DEFAULT_AVATAR_SIZE), Image.ANTIALIAS)
    except IOError:
        raise BadImageError(_("Could not decode image; did you upload an image file?"))
    except DecompressionBombError:
        raise BadImageError(_("Image size exceeds limit."))
    out = io.BytesIO()
    if im.mode == 'CMYK':
        im = im.convert('RGB')
    im.save(out, format='png')
    return out.getvalue()


def resize_gif(im: GifImageFile, size: int=DEFAULT_EMOJI_SIZE) -> bytes:
    frames = []
    duration_info = []
    # If 'loop' info is not set then loop for infinite number of times.
    loop = im.info.get("loop", 0)
    for frame_num in range(0, im.n_frames):
        im.seek(frame_num)
        new_frame = Image.new("RGBA", im.size)
        new_frame.paste(im, (0, 0), im.convert("RGBA"))
        new_frame = ImageOps.fit(new_frame, (size, size), Image.ANTIALIAS)
        frames.append(new_frame)
        duration_info.append(im.info['duration'])
    out = io.BytesIO()
    frames[0].save(out, save_all=True, optimize=True,
                   format="GIF", append_images=frames[1:],
                   duration=duration_info,
                   loop=loop)
    return out.getvalue()


def resize_emoji(image_data: bytes, size: int=DEFAULT_EMOJI_SIZE) -> bytes:
    try:
        im = Image.open(io.BytesIO(image_data))
        image_format = im.format
        if image_format == "GIF":
            # There are a number of bugs in Pillow.GifImagePlugin which cause
            # results in resized gifs being broken. To work around this we
            # only resize under certain conditions to minimize the chance of
            # creating ugly gifs.
            should_resize = any((
                im.size[0] != im.size[1],                            # not square
                im.size[0] > MAX_EMOJI_GIF_SIZE,                     # dimensions too large
                len(image_data) > MAX_EMOJI_GIF_FILE_SIZE_BYTES,     # filesize too large
            ))
            return resize_gif(im, size) if should_resize else image_data
        else:
            im = exif_rotate(im)
            im = ImageOps.fit(im, (size, size), Image.ANTIALIAS)
            out = io.BytesIO()
            im.save(out, format=image_format)
            return out.getvalue()
    except IOError:
        raise BadImageError(_("Could not decode image; did you upload an image file?"))
    except DecompressionBombError:
        raise BadImageError(_("Image size exceeds limit."))


### Common

class ZulipUploadBackend:
    def upload_message_file(self, uploaded_file_name: str, uploaded_file_size: int,
                            content_type: Optional[str], file_data: bytes,
                            user_profile: UserProfile,
                            target_realm: Optional[Realm]=None) -> str:
        raise NotImplementedError()

    def upload_avatar_image(self, user_file: File,
                            acting_user_profile: UserProfile,
                            target_user_profile: UserProfile) -> None:
        raise NotImplementedError()

    def delete_avatar_image(self, user: UserProfile) -> None:
        raise NotImplementedError()

    def delete_message_image(self, path_id: str) -> bool:
        raise NotImplementedError()

    def get_avatar_url(self, hash_key: str, medium: bool=False) -> str:
        raise NotImplementedError()

    def copy_avatar(self, source_profile: UserProfile, target_profile: UserProfile) -> None:
        raise NotImplementedError()

    def ensure_medium_avatar_image(self, user_profile: UserProfile) -> None:
        raise NotImplementedError()

    def ensure_basic_avatar_image(self, user_profile: UserProfile) -> None:
        raise NotImplementedError()

    def upload_realm_icon_image(self, icon_file: File, user_profile: UserProfile) -> None:
        raise NotImplementedError()

    def get_realm_icon_url(self, realm_id: int, version: int) -> str:
        raise NotImplementedError()

    def upload_realm_logo_image(self, logo_file: File, user_profile: UserProfile,
                                night: bool) -> None:
        raise NotImplementedError()

    def get_realm_logo_url(self, realm_id: int, version: int, night: bool) -> str:
        raise NotImplementedError()

    def upload_emoji_image(self, emoji_file: File, emoji_file_name: str, user_profile: UserProfile) -> None:
        raise NotImplementedError()

    def get_emoji_url(self, emoji_file_name: str, realm_id: int) -> str:
        raise NotImplementedError()


### S3

def get_bucket(conn: S3Connection, bucket_name: str) -> Bucket:
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
        bucket_name: str,
        file_name: str,
        content_type: Optional[str],
        user_profile: UserProfile,
        contents: bytes) -> None:

    conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
    bucket = get_bucket(conn, bucket_name)
    key = Key(bucket)
    key.key = file_name
    key.set_metadata("user_profile_id", str(user_profile.id))
    key.set_metadata("realm_id", str(user_profile.realm_id))

    if content_type is not None:
        headers = {'Content-Type': content_type}  # type: Optional[Dict[str, str]]
    else:
        headers = None

    key.set_contents_from_string(contents, headers=headers)  # type: ignore # https://github.com/python/typeshed/issues/1552

def check_upload_within_quota(realm: Realm, uploaded_file_size: int) -> None:
    upload_quota = realm.upload_quota_bytes()
    if upload_quota is None:
        return
    used_space = realm.currently_used_upload_space_bytes()
    if (used_space + uploaded_file_size) > upload_quota:
        raise RealmUploadQuotaError(_("Upload would exceed your organization's upload quota."))

def get_file_info(request: HttpRequest, user_file: File) -> Tuple[str, int, Optional[str]]:

    uploaded_file_name = user_file.name
    assert isinstance(uploaded_file_name, str)

    content_type = request.GET.get('mimetype')
    if content_type is None:
        guessed_type = guess_type(uploaded_file_name)[0]
        if guessed_type is not None:
            content_type = guessed_type
    else:
        extension = guess_extension(content_type)
        if extension is not None:
            uploaded_file_name = uploaded_file_name + extension

    uploaded_file_name = urllib.parse.unquote(uploaded_file_name)
    uploaded_file_size = user_file.size

    return uploaded_file_name, uploaded_file_size, content_type


def get_signed_upload_url(path: str) -> str:
    conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
    return conn.generate_url(15, 'GET', bucket=settings.S3_AUTH_UPLOADS_BUCKET, key=path)

def get_realm_for_filename(path: str) -> Optional[int]:
    conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
    key = get_bucket(conn, settings.S3_AUTH_UPLOADS_BUCKET).get_key(path)
    if key is None:
        # This happens if the key does not exist.
        return None
    return get_user_profile_by_id(key.metadata["user_profile_id"]).realm_id

class S3UploadBackend(ZulipUploadBackend):
    def delete_file_from_s3(self, path_id: str, bucket_name: str) -> bool:
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        bucket = get_bucket(conn, bucket_name)

        # check if file exists
        key = bucket.get_key(path_id)
        if key is not None:
            bucket.delete_key(key)
            return True

        file_name = path_id.split("/")[-1]
        logging.warning("%s does not exist. Its entry in the database will be removed." % (file_name,))
        return False

    def upload_message_file(self, uploaded_file_name: str, uploaded_file_size: int,
                            content_type: Optional[str], file_data: bytes,
                            user_profile: UserProfile, target_realm: Optional[Realm]=None) -> str:
        bucket_name = settings.S3_AUTH_UPLOADS_BUCKET
        if target_realm is None:
            target_realm = user_profile.realm
        s3_file_name = "/".join([
            str(target_realm.id),
            random_name(18),
            sanitize_name(uploaded_file_name)
        ])
        url = "/user_uploads/%s" % (s3_file_name,)

        upload_image_to_s3(
            bucket_name,
            s3_file_name,
            content_type,
            user_profile,
            file_data
        )

        create_attachment(uploaded_file_name, s3_file_name, user_profile, uploaded_file_size)
        return url

    def delete_message_image(self, path_id: str) -> bool:
        return self.delete_file_from_s3(path_id, settings.S3_AUTH_UPLOADS_BUCKET)

    def write_avatar_images(self, s3_file_name: str, target_user_profile: UserProfile,
                            image_data: bytes, content_type: Optional[str]) -> None:
        bucket_name = settings.S3_AVATAR_BUCKET

        upload_image_to_s3(
            bucket_name,
            s3_file_name + ".original",
            content_type,
            target_user_profile,
            image_data,
        )

        # custom 500px wide version
        resized_medium = resize_avatar(image_data, MEDIUM_AVATAR_SIZE)
        upload_image_to_s3(
            bucket_name,
            s3_file_name + "-medium.png",
            "image/png",
            target_user_profile,
            resized_medium
        )

        resized_data = resize_avatar(image_data)
        upload_image_to_s3(
            bucket_name,
            s3_file_name,
            'image/png',
            target_user_profile,
            resized_data,
        )
        # See avatar_url in avatar.py for URL.  (That code also handles the case
        # that users use gravatar.)

    def upload_avatar_image(self, user_file: File,
                            acting_user_profile: UserProfile,
                            target_user_profile: UserProfile) -> None:
        content_type = guess_type(user_file.name)[0]
        s3_file_name = user_avatar_path(target_user_profile)

        image_data = user_file.read()
        self.write_avatar_images(s3_file_name, target_user_profile,
                                 image_data, content_type)

    def delete_avatar_image(self, user: UserProfile) -> None:
        path_id = user_avatar_path(user)
        bucket_name = settings.S3_AVATAR_BUCKET

        self.delete_file_from_s3(path_id + ".original", bucket_name)
        self.delete_file_from_s3(path_id + "-medium.png", bucket_name)
        self.delete_file_from_s3(path_id, bucket_name)

    def get_avatar_key(self, file_name: str) -> Key:
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        bucket_name = settings.S3_AVATAR_BUCKET
        bucket = get_bucket(conn, bucket_name)

        key = bucket.get_key(file_name)
        return key

    def copy_avatar(self, source_profile: UserProfile, target_profile: UserProfile) -> None:
        s3_source_file_name = user_avatar_path(source_profile)
        s3_target_file_name = user_avatar_path(target_profile)

        key = self.get_avatar_key(s3_source_file_name + ".original")
        image_data = key.get_contents_as_string()  # type: ignore # https://github.com/python/typeshed/issues/1552
        content_type = key.content_type

        self.write_avatar_images(s3_target_file_name, target_profile, image_data, content_type)  # type: ignore # image_data is `bytes`, boto subs are wrong

    def get_avatar_url(self, hash_key: str, medium: bool=False) -> str:
        bucket = settings.S3_AVATAR_BUCKET
        medium_suffix = "-medium.png" if medium else ""
        # ?x=x allows templates to append additional parameters with &s
        return "https://%s.s3.amazonaws.com/%s%s?x=x" % (bucket, hash_key, medium_suffix)

    def upload_realm_icon_image(self, icon_file: File, user_profile: UserProfile) -> None:
        content_type = guess_type(icon_file.name)[0]
        bucket_name = settings.S3_AVATAR_BUCKET
        s3_file_name = os.path.join(str(user_profile.realm.id), 'realm', 'icon')

        image_data = icon_file.read()
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
            s3_file_name + ".png",
            'image/png',
            user_profile,
            resized_data,
        )
        # See avatar_url in avatar.py for URL.  (That code also handles the case
        # that users use gravatar.)

    def get_realm_icon_url(self, realm_id: int, version: int) -> str:
        bucket = settings.S3_AVATAR_BUCKET
        # ?x=x allows templates to append additional parameters with &s
        return "https://%s.s3.amazonaws.com/%s/realm/icon.png?version=%s" % (bucket, realm_id, version)

    def upload_realm_logo_image(self, logo_file: File, user_profile: UserProfile,
                                night: bool) -> None:
        content_type = guess_type(logo_file.name)[0]
        bucket_name = settings.S3_AVATAR_BUCKET
        if night:
            basename = 'night_logo'
        else:
            basename = 'logo'
        s3_file_name = os.path.join(str(user_profile.realm.id), 'realm', basename)

        image_data = logo_file.read()
        upload_image_to_s3(
            bucket_name,
            s3_file_name + ".original",
            content_type,
            user_profile,
            image_data,
        )

        resized_data = resize_logo(image_data)
        upload_image_to_s3(
            bucket_name,
            s3_file_name + ".png",
            'image/png',
            user_profile,
            resized_data,
        )
        # See avatar_url in avatar.py for URL.  (That code also handles the case
        # that users use gravatar.)

    def get_realm_logo_url(self, realm_id: int, version: int, night: bool) -> str:
        bucket = settings.S3_AVATAR_BUCKET
        # ?x=x allows templates to append additional parameters with &s
        if not night:
            file_name = 'logo.png'
        else:
            file_name = 'night_logo.png'
        return "https://%s.s3.amazonaws.com/%s/realm/%s?version=%s" % (bucket, realm_id, file_name, version)

    def ensure_medium_avatar_image(self, user_profile: UserProfile) -> None:
        file_path = user_avatar_path(user_profile)
        s3_file_name = file_path

        bucket_name = settings.S3_AVATAR_BUCKET
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        bucket = get_bucket(conn, bucket_name)
        key = bucket.get_key(file_path + ".original")
        image_data = key.get_contents_as_string()

        resized_medium = resize_avatar(image_data, MEDIUM_AVATAR_SIZE)  # type: ignore # image_data is `bytes`, boto subs are wrong
        upload_image_to_s3(
            bucket_name,
            s3_file_name + "-medium.png",
            "image/png",
            user_profile,
            resized_medium
        )

    def ensure_basic_avatar_image(self, user_profile: UserProfile) -> None:  # nocoverage
        # TODO: Refactor this to share code with ensure_medium_avatar_image
        file_path = user_avatar_path(user_profile)
        # Also TODO: Migrate to user_avatar_path(user_profile) + ".png".
        s3_file_name = file_path

        bucket_name = settings.S3_AVATAR_BUCKET
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        bucket = get_bucket(conn, bucket_name)
        key = bucket.get_key(file_path + ".original")
        image_data = key.get_contents_as_string()

        resized_avatar = resize_avatar(image_data)  # type: ignore # image_data is `bytes`, boto subs are wrong
        upload_image_to_s3(
            bucket_name,
            s3_file_name,
            "image/png",
            user_profile,
            resized_avatar
        )

    def upload_emoji_image(self, emoji_file: File, emoji_file_name: str,
                           user_profile: UserProfile) -> None:
        content_type = guess_type(emoji_file.name)[0]
        bucket_name = settings.S3_AVATAR_BUCKET
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=user_profile.realm_id,
            emoji_file_name=emoji_file_name
        )

        image_data = emoji_file.read()
        resized_image_data = resize_emoji(image_data)
        upload_image_to_s3(
            bucket_name,
            ".".join((emoji_path, "original")),
            content_type,
            user_profile,
            image_data,
        )
        upload_image_to_s3(
            bucket_name,
            emoji_path,
            content_type,
            user_profile,
            resized_image_data,
        )

    def get_emoji_url(self, emoji_file_name: str, realm_id: int) -> str:
        bucket = settings.S3_AVATAR_BUCKET
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(realm_id=realm_id,
                                                        emoji_file_name=emoji_file_name)
        return "https://%s.s3.amazonaws.com/%s" % (bucket, emoji_path)


### Local

def write_local_file(type: str, path: str, file_data: bytes) -> None:
    file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, type, path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'wb') as f:
        f.write(file_data)

def read_local_file(type: str, path: str) -> bytes:
    file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, type, path)
    with open(file_path, 'rb') as f:
        return f.read()

def delete_local_file(type: str, path: str) -> bool:
    file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, type, path)
    if os.path.isfile(file_path):
        # This removes the file but the empty folders still remain.
        os.remove(file_path)
        return True
    file_name = path.split("/")[-1]
    logging.warning("%s does not exist. Its entry in the database will be removed." % (file_name,))
    return False

def get_local_file_path(path_id: str) -> Optional[str]:
    local_path = os.path.join(settings.LOCAL_UPLOADS_DIR, 'files', path_id)
    if os.path.isfile(local_path):
        return local_path
    else:
        return None

class LocalUploadBackend(ZulipUploadBackend):
    def upload_message_file(self, uploaded_file_name: str, uploaded_file_size: int,
                            content_type: Optional[str], file_data: bytes,
                            user_profile: UserProfile, target_realm: Optional[Realm]=None) -> str:
        # Split into 256 subdirectories to prevent directories from getting too big
        path = "/".join([
            str(user_profile.realm_id),
            format(random.randint(0, 255), 'x'),
            random_name(18),
            sanitize_name(uploaded_file_name)
        ])

        write_local_file('files', path, file_data)
        create_attachment(uploaded_file_name, path, user_profile, uploaded_file_size)
        return '/user_uploads/' + path

    def delete_message_image(self, path_id: str) -> bool:
        return delete_local_file('files', path_id)

    def write_avatar_images(self, file_path: str, image_data: bytes) -> None:
        write_local_file('avatars', file_path + '.original', image_data)

        resized_data = resize_avatar(image_data)
        write_local_file('avatars', file_path + '.png', resized_data)

        resized_medium = resize_avatar(image_data, MEDIUM_AVATAR_SIZE)
        write_local_file('avatars', file_path + '-medium.png', resized_medium)

    def upload_avatar_image(self, user_file: File,
                            acting_user_profile: UserProfile,
                            target_user_profile: UserProfile) -> None:
        file_path = user_avatar_path(target_user_profile)

        image_data = user_file.read()
        self.write_avatar_images(file_path, image_data)

    def delete_avatar_image(self, user: UserProfile) -> None:
        path_id = user_avatar_path(user)

        delete_local_file("avatars", path_id + ".original")
        delete_local_file("avatars", path_id + ".png")
        delete_local_file("avatars", path_id + "-medium.png")

    def get_avatar_url(self, hash_key: str, medium: bool=False) -> str:
        # ?x=x allows templates to append additional parameters with &s
        medium_suffix = "-medium" if medium else ""
        return "/user_avatars/%s%s.png?x=x" % (hash_key, medium_suffix)

    def copy_avatar(self, source_profile: UserProfile, target_profile: UserProfile) -> None:
        source_file_path = user_avatar_path(source_profile)
        target_file_path = user_avatar_path(target_profile)

        image_data = read_local_file('avatars', source_file_path + '.original')
        self.write_avatar_images(target_file_path, image_data)

    def upload_realm_icon_image(self, icon_file: File, user_profile: UserProfile) -> None:
        upload_path = os.path.join('avatars', str(user_profile.realm.id), 'realm')

        image_data = icon_file.read()
        write_local_file(
            upload_path,
            'icon.original',
            image_data)

        resized_data = resize_avatar(image_data)
        write_local_file(upload_path, 'icon.png', resized_data)

    def get_realm_icon_url(self, realm_id: int, version: int) -> str:
        # ?x=x allows templates to append additional parameters with &s
        return "/user_avatars/%s/realm/icon.png?version=%s" % (realm_id, version)

    def upload_realm_logo_image(self, logo_file: File, user_profile: UserProfile,
                                night: bool) -> None:
        upload_path = os.path.join('avatars', str(user_profile.realm.id), 'realm')
        if night:
            original_file = 'night_logo.original'
            resized_file = 'night_logo.png'
        else:
            original_file = 'logo.original'
            resized_file = 'logo.png'
        image_data = logo_file.read()
        write_local_file(
            upload_path,
            original_file,
            image_data)

        resized_data = resize_logo(image_data)
        write_local_file(upload_path, resized_file, resized_data)

    def get_realm_logo_url(self, realm_id: int, version: int, night: bool) -> str:
        # ?x=x allows templates to append additional parameters with &s
        if night:
            file_name = 'night_logo.png'
        else:
            file_name = 'logo.png'
        return "/user_avatars/%s/realm/%s?version=%s" % (realm_id, file_name, version)

    def ensure_medium_avatar_image(self, user_profile: UserProfile) -> None:
        file_path = user_avatar_path(user_profile)

        output_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", file_path + "-medium.png")
        if os.path.isfile(output_path):
            return

        image_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", file_path + ".original")
        image_data = open(image_path, "rb").read()
        resized_medium = resize_avatar(image_data, MEDIUM_AVATAR_SIZE)
        write_local_file('avatars', file_path + '-medium.png', resized_medium)

    def ensure_basic_avatar_image(self, user_profile: UserProfile) -> None:  # nocoverage
        # TODO: Refactor this to share code with ensure_medium_avatar_image
        file_path = user_avatar_path(user_profile)

        output_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", file_path + ".png")
        if os.path.isfile(output_path):
            return

        image_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", file_path + ".original")
        image_data = open(image_path, "rb").read()
        resized_avatar = resize_avatar(image_data)
        write_local_file('avatars', file_path + '.png', resized_avatar)

    def upload_emoji_image(self, emoji_file: File, emoji_file_name: str,
                           user_profile: UserProfile) -> None:
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id= user_profile.realm_id,
            emoji_file_name=emoji_file_name
        )

        image_data = emoji_file.read()
        resized_image_data = resize_emoji(image_data)
        write_local_file(
            'avatars',
            ".".join((emoji_path, "original")),
            image_data)
        write_local_file(
            'avatars',
            emoji_path,
            resized_image_data)

    def get_emoji_url(self, emoji_file_name: str, realm_id: int) -> str:
        return os.path.join(
            "/user_avatars",
            RealmEmoji.PATH_ID_TEMPLATE.format(realm_id=realm_id, emoji_file_name=emoji_file_name))

# Common and wrappers
if settings.LOCAL_UPLOADS_DIR is not None:
    upload_backend = LocalUploadBackend()  # type: ZulipUploadBackend
else:
    upload_backend = S3UploadBackend()  # nocoverage

def delete_message_image(path_id: str) -> bool:
    return upload_backend.delete_message_image(path_id)

def upload_avatar_image(user_file: File, acting_user_profile: UserProfile,
                        target_user_profile: UserProfile) -> None:
    upload_backend.upload_avatar_image(user_file, acting_user_profile, target_user_profile)

def delete_avatar_image(user_profile: UserProfile) -> None:
    upload_backend.delete_avatar_image(user_profile)

def copy_avatar(source_profile: UserProfile, target_profile: UserProfile) -> None:
    upload_backend.copy_avatar(source_profile, target_profile)

def upload_icon_image(user_file: File, user_profile: UserProfile) -> None:
    upload_backend.upload_realm_icon_image(user_file, user_profile)

def upload_logo_image(user_file: File, user_profile: UserProfile, night: bool) -> None:
    upload_backend.upload_realm_logo_image(user_file, user_profile, night)

def upload_emoji_image(emoji_file: File, emoji_file_name: str, user_profile: UserProfile) -> None:
    upload_backend.upload_emoji_image(emoji_file, emoji_file_name, user_profile)

def upload_message_file(uploaded_file_name: str, uploaded_file_size: int,
                        content_type: Optional[str], file_data: bytes,
                        user_profile: UserProfile, target_realm: Optional[Realm]=None) -> str:
    return upload_backend.upload_message_file(uploaded_file_name, uploaded_file_size,
                                              content_type, file_data, user_profile,
                                              target_realm=target_realm)

def claim_attachment(user_profile: UserProfile,
                     path_id: str,
                     message: Message,
                     is_message_realm_public: bool) -> Attachment:
    attachment = Attachment.objects.get(path_id=path_id)
    attachment.messages.add(message)
    attachment.is_realm_public = attachment.is_realm_public or is_message_realm_public
    attachment.save()
    return attachment

def create_attachment(file_name: str, path_id: str, user_profile: UserProfile,
                      file_size: int) -> bool:
    attachment = Attachment.objects.create(file_name=file_name, path_id=path_id, owner=user_profile,
                                           realm=user_profile.realm, size=file_size)
    from zerver.lib.actions import notify_attachment_update
    notify_attachment_update(user_profile, 'add', attachment.to_dict())
    return True

def upload_message_image_from_request(request: HttpRequest, user_file: File,
                                      user_profile: UserProfile) -> str:
    uploaded_file_name, uploaded_file_size, content_type = get_file_info(request, user_file)
    return upload_message_file(uploaded_file_name, uploaded_file_size,
                               content_type, user_file.read(), user_profile)

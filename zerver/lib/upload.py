import base64
import binascii
import io
import logging
import os
import random
import re
import secrets
import shutil
import unicodedata
import urllib
from datetime import timedelta
from mimetypes import guess_extension, guess_type
from typing import Any, Callable, Optional, Tuple

import boto3
import botocore
from boto3.resources.base import ServiceResource
from boto3.session import Session
from botocore.client import Config
from django.conf import settings
from django.core.files import File
from django.core.signing import BadSignature, TimestampSigner
from django.http import HttpRequest
from django.urls import reverse
from django.utils.translation import ugettext as _
from jinja2 import Markup as mark_safe
from PIL import ExifTags, Image, ImageOps
from PIL.GifImagePlugin import GifImageFile
from PIL.Image import DecompressionBombError

from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.models import Attachment, Message, Realm, RealmEmoji, UserProfile

DEFAULT_AVATAR_SIZE = 100
MEDIUM_AVATAR_SIZE = 500
DEFAULT_EMOJI_SIZE = 64

# These sizes were selected based on looking at the maximum common
# sizes in a library of animated custom emoji, balanced against the
# network cost of very large emoji images.
MAX_EMOJI_GIF_SIZE = 128
MAX_EMOJI_GIF_FILE_SIZE_BYTES = 128 * 1024 * 1024  # 128 kb

# Duration that the signed upload URLs that we redirect to when
# accessing uploaded files are available for clients to fetch before
# they expire.
SIGNED_UPLOAD_URL_DURATION = 60

INLINE_MIME_TYPES = [
    "application/pdf",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
    # To avoid cross-site scripting attacks, DO NOT add types such
    # as application/xhtml+xml, application/x-shockwave-flash,
    # image/svg+xml, text/html, or text/xml.
]

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
    value = re.sub(r'[-\s]+', '-', value, flags=re.U)
    assert value not in {'', '.', '..'}
    return mark_safe(value)

class BadImageError(JsonableError):
    code = ErrorCode.BAD_IMAGE

name_to_tag_num = {name: num for num, name in ExifTags.TAGS.items()}

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
    except OSError:
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
    except OSError:
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
    disposals = []
    # If 'loop' info is not set then loop for infinite number of times.
    loop = im.info.get("loop", 0)
    for frame_num in range(0, im.n_frames):
        im.seek(frame_num)
        new_frame = im.copy()
        new_frame.paste(im, (0, 0), im.convert("RGBA"))
        new_frame = ImageOps.pad(new_frame, (size, size), Image.ANTIALIAS)
        frames.append(new_frame)
        duration_info.append(im.info['duration'])
        disposals.append(im.disposal_method)
    out = io.BytesIO()
    frames[0].save(out, save_all=True, optimize=False,
                   format="GIF", append_images=frames[1:],
                   duration=duration_info,
                   disposal=disposals,
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
            should_resize = (
                im.size[0] != im.size[1]                             # not square
                or im.size[0] > MAX_EMOJI_GIF_SIZE                   # dimensions too large
                or len(image_data) > MAX_EMOJI_GIF_FILE_SIZE_BYTES   # filesize too large
            )
            return resize_gif(im, size) if should_resize else image_data
        else:
            im = exif_rotate(im)
            im = ImageOps.fit(im, (size, size), Image.ANTIALIAS)
            out = io.BytesIO()
            im.save(out, format=image_format)
            return out.getvalue()
    except OSError:
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
                            target_user_profile: UserProfile,
                            content_type: Optional[str]=None) -> None:
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

    def upload_export_tarball(self, realm: Realm, tarball_path: str,
                              percent_callback: Optional[Callable[[Any], None]]=None) -> str:
        raise NotImplementedError()

    def delete_export_tarball(self, export_path: str) -> Optional[str]:
        raise NotImplementedError()

    def get_export_tarball_url(self, realm: Realm, export_path: str) -> str:
        raise NotImplementedError()

    def realm_avatar_and_logo_path(self, realm: Realm) -> str:
        raise NotImplementedError()

### S3

def get_bucket(session: Session, bucket_name: str) -> ServiceResource:
    # See https://github.com/python/typeshed/issues/2706
    # for why this return type is a `ServiceResource`.
    bucket = session.resource('s3').Bucket(bucket_name)
    return bucket

def upload_image_to_s3(
        # See https://github.com/python/typeshed/issues/2706
        bucket: ServiceResource,
        file_name: str,
        content_type: Optional[str],
        user_profile: UserProfile,
        contents: bytes) -> None:
    key = bucket.Object(file_name)
    metadata = {
        "user_profile_id": str(user_profile.id),
        "realm_id": str(user_profile.realm_id),
    }

    content_disposition = ''
    if content_type is None:
        content_type = ''
    if content_type not in INLINE_MIME_TYPES:
        content_disposition = "attachment"

    key.put(Body=contents, Metadata=metadata, ContentType=content_type,
            ContentDisposition=content_disposition)

def check_upload_within_quota(realm: Realm, uploaded_file_size: int) -> None:
    upload_quota = realm.upload_quota_bytes()
    if upload_quota is None:
        return
    used_space = realm.currently_used_upload_space_bytes()
    if (used_space + uploaded_file_size) > upload_quota:
        raise RealmUploadQuotaError(_("Upload would exceed your organization's upload quota."))

def get_file_info(request: HttpRequest, user_file: File) -> Tuple[str, int, Optional[str]]:

    uploaded_file_name = user_file.name
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
    client = boto3.client('s3', aws_access_key_id=settings.S3_KEY,
                          aws_secret_access_key=settings.S3_SECRET_KEY)
    return client.generate_presigned_url(ClientMethod='get_object',
                                         Params={
                                             'Bucket': settings.S3_AUTH_UPLOADS_BUCKET,
                                             'Key': path},
                                         ExpiresIn=SIGNED_UPLOAD_URL_DURATION,
                                         HttpMethod='GET')

class S3UploadBackend(ZulipUploadBackend):
    def __init__(self) -> None:
        self.session = boto3.Session(settings.S3_KEY, settings.S3_SECRET_KEY)

        self.avatar_bucket = get_bucket(self.session, settings.S3_AVATAR_BUCKET)
        network_location = urllib.parse.urlparse(
            self.avatar_bucket.meta.client.meta.endpoint_url).netloc
        self.avatar_bucket_url = f"https://{self.avatar_bucket.name}.{network_location}"

        self.uploads_bucket = get_bucket(self.session, settings.S3_AUTH_UPLOADS_BUCKET)

    def delete_file_from_s3(self, path_id: str, bucket: ServiceResource) -> bool:
        key = bucket.Object(path_id)

        try:
            key.load()
        except botocore.exceptions.ClientError:
            file_name = path_id.split("/")[-1]
            logging.warning("%s does not exist. Its entry in the database will be removed.", file_name)
            return False
        key.delete()
        return True

    def upload_message_file(self, uploaded_file_name: str, uploaded_file_size: int,
                            content_type: Optional[str], file_data: bytes,
                            user_profile: UserProfile, target_realm: Optional[Realm]=None) -> str:
        if target_realm is None:
            target_realm = user_profile.realm
        s3_file_name = "/".join([
            str(target_realm.id),
            secrets.token_urlsafe(18),
            sanitize_name(uploaded_file_name),
        ])
        url = f"/user_uploads/{s3_file_name}"

        upload_image_to_s3(
            self.uploads_bucket,
            s3_file_name,
            content_type,
            user_profile,
            file_data,
        )

        create_attachment(uploaded_file_name, s3_file_name, user_profile, uploaded_file_size)
        return url

    def delete_message_image(self, path_id: str) -> bool:
        return self.delete_file_from_s3(path_id, self.uploads_bucket)

    def write_avatar_images(self, s3_file_name: str, target_user_profile: UserProfile,
                            image_data: bytes, content_type: Optional[str]) -> None:
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name + ".original",
            content_type,
            target_user_profile,
            image_data,
        )

        # custom 500px wide version
        resized_medium = resize_avatar(image_data, MEDIUM_AVATAR_SIZE)
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name + "-medium.png",
            "image/png",
            target_user_profile,
            resized_medium,
        )

        resized_data = resize_avatar(image_data)
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name,
            'image/png',
            target_user_profile,
            resized_data,
        )
        # See avatar_url in avatar.py for URL.  (That code also handles the case
        # that users use gravatar.)

    def upload_avatar_image(self, user_file: File,
                            acting_user_profile: UserProfile,
                            target_user_profile: UserProfile,
                            content_type: Optional[str] = None) -> None:
        if content_type is None:
            content_type = guess_type(user_file.name)[0]
        s3_file_name = user_avatar_path(target_user_profile)

        image_data = user_file.read()
        self.write_avatar_images(s3_file_name, target_user_profile,
                                 image_data, content_type)

    def delete_avatar_image(self, user: UserProfile) -> None:
        path_id = user_avatar_path(user)

        self.delete_file_from_s3(path_id + ".original", self.avatar_bucket)
        self.delete_file_from_s3(path_id + "-medium.png", self.avatar_bucket)
        self.delete_file_from_s3(path_id, self.avatar_bucket)

    def get_avatar_key(self, file_name: str) -> ServiceResource:
        # See https://github.com/python/typeshed/issues/2706
        # for why this return type is a `ServiceResource`.
        key = self.avatar_bucket.Object(file_name)
        return key

    def copy_avatar(self, source_profile: UserProfile, target_profile: UserProfile) -> None:
        s3_source_file_name = user_avatar_path(source_profile)
        s3_target_file_name = user_avatar_path(target_profile)

        key = self.get_avatar_key(s3_source_file_name + ".original")
        image_data = key.get()['Body'].read()
        content_type = key.content_type

        self.write_avatar_images(s3_target_file_name, target_profile, image_data, content_type)

    def get_avatar_url(self, hash_key: str, medium: bool=False) -> str:
        medium_suffix = "-medium.png" if medium else ""
        # ?x=x allows templates to append additional parameters with &s
        return f"{self.avatar_bucket_url}/{hash_key}{medium_suffix}?x=x"

    def get_export_tarball_url(self, realm: Realm, export_path: str) -> str:
        # export_path has a leading /
        return f"{self.avatar_bucket_url}{export_path}"

    def realm_avatar_and_logo_path(self, realm: Realm) -> str:
        return os.path.join(str(realm.id), 'realm')

    def upload_realm_icon_image(self, icon_file: File, user_profile: UserProfile) -> None:
        content_type = guess_type(icon_file.name)[0]
        s3_file_name = os.path.join(self.realm_avatar_and_logo_path(user_profile.realm), 'icon')

        image_data = icon_file.read()
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name + ".original",
            content_type,
            user_profile,
            image_data,
        )

        resized_data = resize_avatar(image_data)
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name + ".png",
            'image/png',
            user_profile,
            resized_data,
        )
        # See avatar_url in avatar.py for URL.  (That code also handles the case
        # that users use gravatar.)

    def get_realm_icon_url(self, realm_id: int, version: int) -> str:
        # ?x=x allows templates to append additional parameters with &s
        return f"{self.avatar_bucket_url}/{realm_id}/realm/icon.png?version={version}"

    def upload_realm_logo_image(self, logo_file: File, user_profile: UserProfile,
                                night: bool) -> None:
        content_type = guess_type(logo_file.name)[0]
        if night:
            basename = 'night_logo'
        else:
            basename = 'logo'
        s3_file_name = os.path.join(self.realm_avatar_and_logo_path(user_profile.realm), basename)

        image_data = logo_file.read()
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name + ".original",
            content_type,
            user_profile,
            image_data,
        )

        resized_data = resize_logo(image_data)
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name + ".png",
            'image/png',
            user_profile,
            resized_data,
        )
        # See avatar_url in avatar.py for URL.  (That code also handles the case
        # that users use gravatar.)

    def get_realm_logo_url(self, realm_id: int, version: int, night: bool) -> str:
        # ?x=x allows templates to append additional parameters with &s
        if not night:
            file_name = 'logo.png'
        else:
            file_name = 'night_logo.png'
        return f"{self.avatar_bucket_url}/{realm_id}/realm/{file_name}?version={version}"

    def ensure_medium_avatar_image(self, user_profile: UserProfile) -> None:
        file_path = user_avatar_path(user_profile)
        s3_file_name = file_path

        key = self.avatar_bucket.Object(file_path + ".original")
        image_data = key.get()['Body'].read()

        resized_medium = resize_avatar(image_data, MEDIUM_AVATAR_SIZE)
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name + "-medium.png",
            "image/png",
            user_profile,
            resized_medium,
        )

    def ensure_basic_avatar_image(self, user_profile: UserProfile) -> None:  # nocoverage
        # TODO: Refactor this to share code with ensure_medium_avatar_image
        file_path = user_avatar_path(user_profile)
        # Also TODO: Migrate to user_avatar_path(user_profile) + ".png".
        s3_file_name = file_path

        key = self.avatar_bucket.Object(file_path + ".original")
        image_data = key.get()['Body'].read()

        resized_avatar = resize_avatar(image_data)
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name,
            "image/png",
            user_profile,
            resized_avatar,
        )

    def upload_emoji_image(self, emoji_file: File, emoji_file_name: str,
                           user_profile: UserProfile) -> None:
        content_type = guess_type(emoji_file.name)[0]
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=user_profile.realm_id,
            emoji_file_name=emoji_file_name,
        )

        image_data = emoji_file.read()
        resized_image_data = resize_emoji(image_data)
        upload_image_to_s3(
            self.avatar_bucket,
            ".".join((emoji_path, "original")),
            content_type,
            user_profile,
            image_data,
        )
        upload_image_to_s3(
            self.avatar_bucket,
            emoji_path,
            content_type,
            user_profile,
            resized_image_data,
        )

    def get_emoji_url(self, emoji_file_name: str, realm_id: int) -> str:
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(realm_id=realm_id,
                                                        emoji_file_name=emoji_file_name)
        return f"{self.avatar_bucket_url}/{emoji_path}"

    def upload_export_tarball(self, realm: Optional[Realm], tarball_path: str,
                              percent_callback: Optional[Callable[[Any], None]]=None) -> str:
        # We use the avatar bucket, because it's world-readable.
        key = self.avatar_bucket.Object(os.path.join("exports", secrets.token_hex(16),
                                                     os.path.basename(tarball_path)))

        key.upload_file(tarball_path, Callback=percent_callback)

        session = botocore.session.get_session()
        config = Config(signature_version=botocore.UNSIGNED)

        public_url = session.create_client('s3', config=config).generate_presigned_url(
            'get_object',
            Params={
                'Bucket': self.avatar_bucket.name,
                'Key': key.key,
            },
            ExpiresIn=0,
        )
        return public_url

    def delete_export_tarball(self, export_path: str) -> Optional[str]:
        assert export_path.startswith("/")
        path_id = export_path[1:]
        if self.delete_file_from_s3(path_id, self.avatar_bucket):
            return export_path
        return None

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
    logging.warning("%s does not exist. Its entry in the database will be removed.", file_name)
    return False

def get_local_file_path(path_id: str) -> Optional[str]:
    local_path = os.path.join(settings.LOCAL_UPLOADS_DIR, 'files', path_id)
    if os.path.isfile(local_path):
        return local_path
    else:
        return None

LOCAL_FILE_ACCESS_TOKEN_SALT = "local_file_"

def generate_unauthed_file_access_url(path_id: str) -> str:
    signed_data = TimestampSigner(salt=LOCAL_FILE_ACCESS_TOKEN_SALT).sign(path_id)
    token = base64.b16encode(signed_data.encode('utf-8')).decode('utf-8')

    filename = path_id.split('/')[-1]
    return reverse('local_file_unauthed', args=[token, filename])

def get_local_file_path_id_from_token(token: str) -> Optional[str]:
    signer = TimestampSigner(salt=LOCAL_FILE_ACCESS_TOKEN_SALT)
    try:
        signed_data = base64.b16decode(token).decode('utf-8')
        path_id = signer.unsign(signed_data, max_age=timedelta(seconds=60))
    except (BadSignature, binascii.Error):
        return None

    return path_id

class LocalUploadBackend(ZulipUploadBackend):
    def upload_message_file(self, uploaded_file_name: str, uploaded_file_size: int,
                            content_type: Optional[str], file_data: bytes,
                            user_profile: UserProfile, target_realm: Optional[Realm]=None) -> str:
        # Split into 256 subdirectories to prevent directories from getting too big
        path = "/".join([
            str(user_profile.realm_id),
            format(random.randint(0, 255), 'x'),
            secrets.token_urlsafe(18),
            sanitize_name(uploaded_file_name),
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
                            target_user_profile: UserProfile,
                            content_type: Optional[str] = None) -> None:
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
        return f"/user_avatars/{hash_key}{medium_suffix}.png?x=x"

    def copy_avatar(self, source_profile: UserProfile, target_profile: UserProfile) -> None:
        source_file_path = user_avatar_path(source_profile)
        target_file_path = user_avatar_path(target_profile)

        image_data = read_local_file('avatars', source_file_path + '.original')
        self.write_avatar_images(target_file_path, image_data)

    def realm_avatar_and_logo_path(self, realm: Realm) -> str:
        return os.path.join('avatars', str(realm.id), 'realm')

    def upload_realm_icon_image(self, icon_file: File, user_profile: UserProfile) -> None:
        upload_path = self.realm_avatar_and_logo_path(user_profile.realm)
        image_data = icon_file.read()
        write_local_file(
            upload_path,
            'icon.original',
            image_data)

        resized_data = resize_avatar(image_data)
        write_local_file(upload_path, 'icon.png', resized_data)

    def get_realm_icon_url(self, realm_id: int, version: int) -> str:
        # ?x=x allows templates to append additional parameters with &s
        return f"/user_avatars/{realm_id}/realm/icon.png?version={version}"

    def upload_realm_logo_image(self, logo_file: File, user_profile: UserProfile,
                                night: bool) -> None:
        upload_path = self.realm_avatar_and_logo_path(user_profile.realm)
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
        return f"/user_avatars/{realm_id}/realm/{file_name}?version={version}"

    def ensure_medium_avatar_image(self, user_profile: UserProfile) -> None:
        file_path = user_avatar_path(user_profile)

        output_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", file_path + "-medium.png")
        if os.path.isfile(output_path):
            return

        image_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", file_path + ".original")
        with open(image_path, "rb") as f:
            image_data = f.read()
        resized_medium = resize_avatar(image_data, MEDIUM_AVATAR_SIZE)
        write_local_file('avatars', file_path + '-medium.png', resized_medium)

    def ensure_basic_avatar_image(self, user_profile: UserProfile) -> None:  # nocoverage
        # TODO: Refactor this to share code with ensure_medium_avatar_image
        file_path = user_avatar_path(user_profile)

        output_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", file_path + ".png")
        if os.path.isfile(output_path):
            return

        image_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", file_path + ".original")
        with open(image_path, "rb") as f:
            image_data = f.read()
        resized_avatar = resize_avatar(image_data)
        write_local_file('avatars', file_path + '.png', resized_avatar)

    def upload_emoji_image(self, emoji_file: File, emoji_file_name: str,
                           user_profile: UserProfile) -> None:
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id= user_profile.realm_id,
            emoji_file_name=emoji_file_name,
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

    def upload_export_tarball(self, realm: Realm, tarball_path: str,
                              percent_callback: Optional[Callable[[Any], None]]=None) -> str:
        path = os.path.join(
            'exports',
            str(realm.id),
            secrets.token_urlsafe(18),
            os.path.basename(tarball_path),
        )
        abs_path = os.path.join(settings.LOCAL_UPLOADS_DIR, 'avatars', path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        shutil.copy(tarball_path, abs_path)
        public_url = realm.uri + '/user_avatars/' + path
        return public_url

    def delete_export_tarball(self, export_path: str) -> Optional[str]:
        # Get the last element of a list in the form ['user_avatars', '<file_path>']
        assert export_path.startswith("/")
        file_path = export_path[1:].split('/', 1)[-1]
        if delete_local_file('avatars', file_path):
            return export_path
        return None

    def get_export_tarball_url(self, realm: Realm, export_path: str) -> str:
        # export_path has a leading `/`
        return realm.uri + export_path

# Common and wrappers
if settings.LOCAL_UPLOADS_DIR is not None:
    upload_backend: ZulipUploadBackend = LocalUploadBackend()
else:
    upload_backend = S3UploadBackend()  # nocoverage

def delete_message_image(path_id: str) -> bool:
    return upload_backend.delete_message_image(path_id)

def upload_avatar_image(user_file: File, acting_user_profile: UserProfile,
                        target_user_profile: UserProfile,
                        content_type: Optional[str]=None) -> None:
    upload_backend.upload_avatar_image(user_file, acting_user_profile,
                                       target_user_profile, content_type=content_type)

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
                     is_message_realm_public: bool,
                     is_message_web_public: bool=False) -> Attachment:
    attachment = Attachment.objects.get(path_id=path_id)
    attachment.messages.add(message)
    attachment.is_web_public = attachment.is_web_public or is_message_web_public
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

def upload_export_tarball(realm: Realm, tarball_path: str,
                          percent_callback: Optional[Callable[[Any], None]]=None) -> str:
    return upload_backend.upload_export_tarball(realm, tarball_path,
                                                percent_callback=percent_callback)

def delete_export_tarball(export_path: str) -> Optional[str]:
    return upload_backend.delete_export_tarball(export_path)

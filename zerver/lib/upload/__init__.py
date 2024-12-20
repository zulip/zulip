import io
import logging
import os
import re
import unicodedata
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import IO, Any
from urllib.parse import unquote, urljoin

import pyvips
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils.translation import gettext as _

from zerver.lib.avatar_hash import user_avatar_base_path_from_ids, user_avatar_path
from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.mime_types import INLINE_MIME_TYPES, guess_type
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.thumbnail import (
    MAX_EMOJI_GIF_FILE_SIZE_BYTES,
    MEDIUM_AVATAR_SIZE,
    THUMBNAIL_ACCEPT_IMAGE_TYPES,
    BadImageError,
    maybe_thumbnail,
    resize_avatar,
    resize_emoji,
)
from zerver.lib.upload.base import StreamingSourceWithSize, ZulipUploadBackend
from zerver.models import Attachment, Message, Realm, RealmEmoji, ScheduledMessage, UserProfile
from zerver.models.users import is_cross_realm_bot_email


class RealmUploadQuotaError(JsonableError):
    code = ErrorCode.REALM_UPLOAD_QUOTA


def check_upload_within_quota(realm: Realm, uploaded_file_size: int) -> None:
    upload_quota = realm.upload_quota_bytes()
    if upload_quota is None:
        return
    used_space = realm.currently_used_upload_space_bytes()
    if (used_space + uploaded_file_size) > upload_quota:
        raise RealmUploadQuotaError(_("Upload would exceed your organization's upload quota."))


def create_attachment(
    file_name: str,
    path_id: str,
    content_type: str,
    file_data: bytes | StreamingSourceWithSize,
    user_profile: UserProfile,
    realm: Realm,
) -> None:
    assert (user_profile.realm_id == realm.id) or is_cross_realm_bot_email(
        user_profile.delivery_email
    )
    if isinstance(file_data, bytes):
        file_size = len(file_data)
        file_real_data: bytes | pyvips.Source = file_data
    else:
        file_size = file_data.size
        file_real_data = file_data.source
    attachment = Attachment.objects.create(
        file_name=file_name,
        path_id=path_id,
        owner=user_profile,
        realm=realm,
        size=file_size,
        content_type=content_type,
    )
    maybe_thumbnail(file_real_data, content_type, path_id, realm.id)
    from zerver.actions.uploads import notify_attachment_update

    notify_attachment_update(user_profile, "add", attachment.to_dict())


def get_file_info(user_file: UploadedFile) -> tuple[str, str]:
    uploaded_file_name = user_file.name
    assert uploaded_file_name is not None

    content_type = user_file.content_type
    # It appears Django's UploadedFile.content_type defaults to an empty string,
    # even though the value is documented as `str | None`. So we check for both.
    if content_type is None or content_type == "":
        guessed_type = guess_type(uploaded_file_name)[0]
        if guessed_type is not None:
            content_type = guessed_type
        else:
            # Fallback to application/octet-stream if unable to determine a
            # different content-type from the filename.
            content_type = "application/octet-stream"

    uploaded_file_name = unquote(uploaded_file_name)

    return uploaded_file_name, content_type


# Common and wrappers
if settings.LOCAL_UPLOADS_DIR is not None:
    from zerver.lib.upload.local import LocalUploadBackend

    upload_backend: ZulipUploadBackend = LocalUploadBackend()
else:  # nocoverage
    from zerver.lib.upload.s3 import S3UploadBackend

    upload_backend = S3UploadBackend()

# Message attachment uploads


def get_public_upload_root_url() -> str:
    return upload_backend.get_public_upload_root_url()


def sanitize_name(value: str, *, strict: bool = False) -> str:
    """Sanitizes a value to be safe to store in a Linux filesystem, in
    S3, and in a URL.  So Unicode is allowed, but not special
    characters other than ".", "-", and "_".

    In "strict" mode, it does not allow Unicode, allowing only ASCII
    [A-Za-z0-9_] as word characters.  This is for the benefit of tusd,
    which is not Unicode-aware.

    This implementation is based on django.utils.text.slugify; it is
    modified by:
    * adding '.' to the list of allowed characters.
    * preserving the case of the value.
    * not stripping trailing dashes and underscores.

    """
    if strict:
        value = re.sub(r"[^A-Za-z0-9_ .-]", "", value).strip()
    else:
        value = unicodedata.normalize("NFKC", value)
        value = re.sub(r"[^\w\s.-]", "", value).strip()
    value = re.sub(r"[-\s]+", "-", value)

    # Django's MultiPartParser never returns files named this, but we
    # could get them after removing spaces; change the name to a safer
    # value.
    if value in {"", ".", ".."}:
        return "uploaded-file"
    return value


def upload_message_attachment(
    uploaded_file_name: str,
    content_type: str,
    file_data: bytes,
    user_profile: UserProfile,
    target_realm: Realm | None = None,
) -> tuple[str, str]:
    if target_realm is None:
        target_realm = user_profile.realm
    path_id = upload_backend.generate_message_upload_path(
        str(target_realm.id), sanitize_name(uploaded_file_name)
    )

    with transaction.atomic(durable=True):
        upload_backend.upload_message_attachment(
            path_id,
            uploaded_file_name,
            content_type,
            file_data,
            user_profile,
        )
        create_attachment(
            uploaded_file_name,
            path_id,
            content_type,
            file_data,
            user_profile,
            target_realm,
        )
    return f"/user_uploads/{path_id}", uploaded_file_name


def claim_attachment(
    path_id: str,
    message: Message | ScheduledMessage,
    is_message_realm_public: bool,
    is_message_web_public: bool = False,
) -> Attachment:
    attachment = Attachment.objects.get(path_id=path_id)
    if isinstance(message, ScheduledMessage):
        attachment.scheduled_messages.add(message)
        # Setting the is_web_public and is_realm_public flags would be incorrect
        # in the scheduled message case - since the attachment becomes such only
        # when the message is actually posted.
        return attachment

    assert isinstance(message, Message)
    attachment.messages.add(message)
    attachment.is_web_public = attachment.is_web_public or is_message_web_public
    attachment.is_realm_public = attachment.is_realm_public or is_message_realm_public
    attachment.save()
    return attachment


def upload_message_attachment_from_request(
    user_file: UploadedFile, user_profile: UserProfile
) -> tuple[str, str]:
    uploaded_file_name, content_type = get_file_info(user_file)
    return upload_message_attachment(
        uploaded_file_name, content_type, user_file.read(), user_profile
    )


def attachment_vips_source(path_id: str) -> StreamingSourceWithSize:
    return upload_backend.attachment_vips_source(path_id)


def save_attachment_contents(path_id: str, filehandle: IO[bytes]) -> None:
    return upload_backend.save_attachment_contents(path_id, filehandle)


def delete_message_attachment(path_id: str) -> bool:
    return upload_backend.delete_message_attachment(path_id)


def delete_message_attachments(path_ids: list[str]) -> None:
    return upload_backend.delete_message_attachments(path_ids)


def all_message_attachments(
    *, include_thumbnails: bool = False, prefix: str = ""
) -> Iterator[tuple[str, datetime]]:
    return upload_backend.all_message_attachments(include_thumbnails, prefix)


# Avatar image uploads


def get_avatar_url(hash_key: str, medium: bool = False) -> str:
    return upload_backend.get_avatar_url(hash_key, medium)


def write_avatar_images(
    file_path: str,
    user_profile: UserProfile,
    image_data: bytes,
    *,
    content_type: str | None,
    backend: ZulipUploadBackend | None = None,
    future: bool = True,
) -> None:
    if backend is None:
        backend = upload_backend
    backend.upload_single_avatar_image(
        file_path + ".original",
        user_profile=user_profile,
        image_data=image_data,
        content_type=content_type,
        future=future,
    )

    backend.upload_single_avatar_image(
        backend.get_avatar_path(file_path, medium=False),
        user_profile=user_profile,
        image_data=resize_avatar(image_data),
        content_type="image/png",
        future=future,
    )

    backend.upload_single_avatar_image(
        backend.get_avatar_path(file_path, medium=True),
        user_profile=user_profile,
        image_data=resize_avatar(image_data, MEDIUM_AVATAR_SIZE),
        content_type="image/png",
        future=future,
    )


def upload_avatar_image(
    user_file: IO[bytes],
    user_profile: UserProfile,
    content_type: str | None = None,
    backend: ZulipUploadBackend | None = None,
    future: bool = True,
) -> None:
    if content_type is None:
        content_type = guess_type(user_file.name)[0]
    if content_type not in THUMBNAIL_ACCEPT_IMAGE_TYPES:
        raise BadImageError(_("Invalid image format"))
    file_path = user_avatar_path(user_profile, future=future)

    image_data = user_file.read()
    write_avatar_images(
        file_path,
        user_profile,
        image_data,
        content_type=content_type,
        backend=backend,
        future=future,
    )


def copy_avatar(source_profile: UserProfile, target_profile: UserProfile) -> None:
    source_file_path = user_avatar_path(source_profile, future=False)
    target_file_path = user_avatar_path(target_profile, future=True)

    image_data, content_type = upload_backend.get_avatar_contents(source_file_path)
    write_avatar_images(
        target_file_path, target_profile, image_data, content_type=content_type, future=True
    )


def ensure_avatar_image(user_profile: UserProfile, medium: bool = False) -> None:
    file_path = user_avatar_path(user_profile)

    final_file_path = upload_backend.get_avatar_path(file_path, medium)

    if settings.LOCAL_AVATARS_DIR is not None:
        output_path = os.path.join(
            settings.LOCAL_AVATARS_DIR,
            final_file_path,
        )

        if os.path.isfile(output_path):
            return

    image_data, _ = upload_backend.get_avatar_contents(file_path)

    if medium:
        resized_avatar = resize_avatar(image_data, MEDIUM_AVATAR_SIZE)
    else:
        resized_avatar = resize_avatar(image_data)
    upload_backend.upload_single_avatar_image(
        final_file_path,
        user_profile=user_profile,
        image_data=resized_avatar,
        content_type="image/png",
        future=False,
    )


def delete_avatar_image(user_profile: UserProfile, avatar_version: int) -> None:
    path_id = user_avatar_base_path_from_ids(user_profile.id, avatar_version, user_profile.realm_id)
    upload_backend.delete_avatar_image(path_id)


# Realm icon and logo uploads


def upload_icon_image(user_file: IO[bytes], user_profile: UserProfile, content_type: str) -> None:
    if content_type not in THUMBNAIL_ACCEPT_IMAGE_TYPES:
        raise BadImageError(_("Invalid image format"))
    upload_backend.upload_realm_icon_image(user_file, user_profile, content_type)


def upload_logo_image(
    user_file: IO[bytes], user_profile: UserProfile, night: bool, content_type: str
) -> None:
    if content_type not in THUMBNAIL_ACCEPT_IMAGE_TYPES:
        raise BadImageError(_("Invalid image format"))
    upload_backend.upload_realm_logo_image(user_file, user_profile, night, content_type)


# Realm emoji uploads


def upload_emoji_image(
    emoji_file: IO[bytes],
    emoji_file_name: str,
    user_profile: UserProfile,
    content_type: str,
    backend: ZulipUploadBackend | None = None,
) -> bool:
    if backend is None:
        backend = upload_backend

    # Emoji are served in the format that they are uploaded, so must
    # be _both_ an image format that we're willing to thumbnail, _and_
    # a format which is widespread enough that we're willing to inline
    # it.  The latter contains non-image formats, but the former
    # limits to only images.
    if content_type not in THUMBNAIL_ACCEPT_IMAGE_TYPES or content_type not in INLINE_MIME_TYPES:
        raise BadImageError(_("Invalid image format"))

    emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
        realm_id=user_profile.realm_id,
        emoji_file_name=emoji_file_name,
    )

    image_data = emoji_file.read()
    backend.upload_single_emoji_image(
        f"{emoji_path}.original", content_type, user_profile, image_data
    )
    resized_image_data, still_image_data = resize_emoji(image_data, emoji_file_name)
    if still_image_data is not None:
        if len(still_image_data) > MAX_EMOJI_GIF_FILE_SIZE_BYTES:  # nocoverage
            raise BadImageError(_("Image size exceeds limit"))
    elif len(resized_image_data) > MAX_EMOJI_GIF_FILE_SIZE_BYTES:  # nocoverage
        raise BadImageError(_("Image size exceeds limit"))
    backend.upload_single_emoji_image(emoji_path, content_type, user_profile, resized_image_data)
    if still_image_data is None:
        return False

    still_path = RealmEmoji.STILL_PATH_ID_TEMPLATE.format(
        realm_id=user_profile.realm_id,
        emoji_filename_without_extension=os.path.splitext(emoji_file_name)[0],
    )
    backend.upload_single_emoji_image(still_path, "image/png", user_profile, still_image_data)
    return True


def get_emoji_file_content(
    session: OutgoingSession, emoji_url: str, emoji_id: int, logger: logging.Logger
) -> tuple[bytes, str]:  # nocoverage
    original_emoji_url = emoji_url + ".original"

    logger.info("Downloading %s", original_emoji_url)
    response = session.get(original_emoji_url)
    if response.status_code == 200:
        assert isinstance(response.content, bytes)
        return response.content, response.headers["Content-Type"]

    logger.info("Error fetching emoji from URL %s", original_emoji_url)
    logger.info("Trying %s instead", emoji_url)
    response = session.get(emoji_url)
    if response.status_code == 200:
        assert isinstance(response.content, bytes)
        return response.content, response.headers["Content-Type"]
    logger.info("Error fetching emoji from URL %s", emoji_url)
    logger.error("Could not fetch emoji %s", emoji_id)
    raise AssertionError(f"Could not fetch emoji {emoji_id}")


def handle_reupload_emojis_event(realm: Realm, logger: logging.Logger) -> None:  # nocoverage
    from zerver.lib.emoji import get_emoji_url

    session = OutgoingSession(role="reupload_emoji", timeout=3, max_retries=3)

    query = RealmEmoji.objects.filter(realm=realm).order_by("id")

    for realm_emoji in query:
        logger.info("Processing emoji %s", realm_emoji.id)
        emoji_filename = realm_emoji.file_name
        assert emoji_filename is not None
        emoji_url = get_emoji_url(emoji_filename, realm_emoji.realm_id)
        if emoji_url.startswith("/"):
            emoji_url = urljoin(realm_emoji.realm.url, emoji_url)

        emoji_file_content, content_type = get_emoji_file_content(
            session, emoji_url, realm_emoji.id, logger
        )

        emoji_bytes_io = io.BytesIO(emoji_file_content)

        user_profile = realm_emoji.author
        # When this runs, emojis have already been migrated to always have .author set.
        assert user_profile is not None

        logger.info("Reuploading emoji %s", realm_emoji.id)
        realm_emoji.is_animated = upload_emoji_image(
            emoji_bytes_io, emoji_filename, user_profile, content_type
        )
        realm_emoji.save(update_fields=["is_animated"])


# Export tarballs


def upload_export_tarball(
    realm: Realm, tarball_path: str, percent_callback: Callable[[Any], None] | None = None
) -> str:
    return upload_backend.upload_export_tarball(
        realm, tarball_path, percent_callback=percent_callback
    )


def delete_export_tarball(export_path: str) -> str | None:
    return upload_backend.delete_export_tarball(export_path)

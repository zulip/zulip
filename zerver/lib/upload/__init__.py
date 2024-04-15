import io
import logging
from datetime import datetime
from mimetypes import guess_type
from typing import IO, Any, BinaryIO, Callable, Iterator, List, Optional, Tuple, Union
from urllib.parse import unquote, urljoin

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext as _

from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.upload.base import ZulipUploadBackend
from zerver.models import Attachment, Message, Realm, RealmEmoji, ScheduledMessage, UserProfile


class RealmUploadQuotaError(JsonableError):
    code = ErrorCode.REALM_UPLOAD_QUOTA


def check_upload_within_quota(realm: Realm, uploaded_file_size: int) -> None:
    upload_quota = realm.upload_quota_bytes()
    if upload_quota is None:
        return
    used_space = realm.currently_used_upload_space_bytes()
    if (used_space + uploaded_file_size) > upload_quota:
        raise RealmUploadQuotaError(_("Upload would exceed your organization's upload quota."))


def get_file_info(user_file: UploadedFile) -> Tuple[str, str]:
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


def upload_message_attachment(
    uploaded_file_name: str,
    uploaded_file_size: int,
    content_type: Optional[str],
    file_data: bytes,
    user_profile: UserProfile,
    target_realm: Optional[Realm] = None,
) -> str:
    return upload_backend.upload_message_attachment(
        uploaded_file_name,
        uploaded_file_size,
        content_type,
        file_data,
        user_profile,
        target_realm=target_realm,
    )


def claim_attachment(
    user_profile: UserProfile,
    path_id: str,
    message: Union[Message, ScheduledMessage],
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
    user_file: UploadedFile, user_profile: UserProfile, user_file_size: int
) -> str:
    uploaded_file_name, content_type = get_file_info(user_file)
    return upload_message_attachment(
        uploaded_file_name, user_file_size, content_type, user_file.read(), user_profile
    )


def save_attachment_contents(path_id: str, filehandle: BinaryIO) -> None:
    return upload_backend.save_attachment_contents(path_id, filehandle)


def delete_message_attachment(path_id: str) -> bool:
    return upload_backend.delete_message_attachment(path_id)


def delete_message_attachments(path_ids: List[str]) -> None:
    return upload_backend.delete_message_attachments(path_ids)


def all_message_attachments() -> Iterator[Tuple[str, datetime]]:
    return upload_backend.all_message_attachments()


# Avatar image uploads


def get_avatar_url(hash_key: str, medium: bool = False) -> str:
    return upload_backend.get_avatar_url(hash_key, medium)


def upload_avatar_image(
    user_file: IO[bytes],
    acting_user_profile: UserProfile,
    target_user_profile: UserProfile,
    content_type: Optional[str] = None,
) -> None:
    upload_backend.upload_avatar_image(
        user_file, acting_user_profile, target_user_profile, content_type=content_type
    )


def copy_avatar(source_profile: UserProfile, target_profile: UserProfile) -> None:
    upload_backend.copy_avatar(source_profile, target_profile)


def delete_avatar_image(user_profile: UserProfile) -> None:
    upload_backend.delete_avatar_image(user_profile)


# Realm icon and logo uploads


def upload_icon_image(user_file: IO[bytes], user_profile: UserProfile) -> None:
    upload_backend.upload_realm_icon_image(user_file, user_profile)


def upload_logo_image(user_file: IO[bytes], user_profile: UserProfile, night: bool) -> None:
    upload_backend.upload_realm_logo_image(user_file, user_profile, night)


# Realm emoji uploads


def upload_emoji_image(
    emoji_file: IO[bytes], emoji_file_name: str, user_profile: UserProfile
) -> bool:
    return upload_backend.upload_emoji_image(emoji_file, emoji_file_name, user_profile)


def get_emoji_file_content(
    session: OutgoingSession, emoji_url: str, emoji_id: int, logger: logging.Logger
) -> bytes:  # nocoverage
    original_emoji_url = emoji_url + ".original"

    logger.info("Downloading %s", original_emoji_url)
    response = session.get(original_emoji_url)
    if response.status_code == 200:
        assert isinstance(response.content, bytes)
        return response.content

    logger.info("Error fetching emoji from URL %s", original_emoji_url)
    logger.info("Trying %s instead", emoji_url)
    response = session.get(emoji_url)
    if response.status_code == 200:
        assert isinstance(response.content, bytes)
        return response.content
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
            emoji_url = urljoin(realm_emoji.realm.uri, emoji_url)

        emoji_file_content = get_emoji_file_content(session, emoji_url, realm_emoji.id, logger)

        emoji_bytes_io = io.BytesIO(emoji_file_content)

        user_profile = realm_emoji.author
        # When this runs, emojis have already been migrated to always have .author set.
        assert user_profile is not None

        logger.info("Reuploading emoji %s", realm_emoji.id)
        realm_emoji.is_animated = upload_emoji_image(emoji_bytes_io, emoji_filename, user_profile)
        realm_emoji.save(update_fields=["is_animated"])


# Export tarballs


def upload_export_tarball(
    realm: Realm, tarball_path: str, percent_callback: Optional[Callable[[Any], None]] = None
) -> str:
    return upload_backend.upload_export_tarball(
        realm, tarball_path, percent_callback=percent_callback
    )


def delete_export_tarball(export_path: str) -> Optional[str]:
    return upload_backend.delete_export_tarball(export_path)

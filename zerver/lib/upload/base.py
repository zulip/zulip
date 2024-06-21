import os
import re
import unicodedata
from datetime import datetime
from typing import IO, Any, BinaryIO, Callable, Iterator, List, Optional, Tuple

from zerver.models import Attachment, Realm, UserProfile
from zerver.models.users import is_cross_realm_bot_email

INLINE_MIME_TYPES = [
    "application/pdf",
    "audio/aac",
    "audio/flac",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/webm",
    "image/apng",
    "image/avif",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
    "video/mp4",
    "video/webm",
    # To avoid cross-site scripting attacks, DO NOT add types such
    # as application/xhtml+xml, application/x-shockwave-flash,
    # image/svg+xml, text/html, or text/xml.
]


def sanitize_name(value: str) -> str:
    """
    Sanitizes a value to be safe to store in a Linux filesystem, in
    S3, and in a URL.  So Unicode is allowed, but not special
    characters other than ".", "-", and "_".

    This implementation is based on django.utils.text.slugify; it is
    modified by:
    * adding '.' to the list of allowed characters.
    * preserving the case of the value.
    * not stripping trailing dashes and underscores.
    """
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"[^\w\s.-]", "", value).strip()
    value = re.sub(r"[-\s]+", "-", value)
    if value in {"", ".", ".."}:
        return "uploaded-file"
    return value


class ZulipUploadBackend:
    # Message attachment uploads
    def get_public_upload_root_url(self) -> str:
        raise NotImplementedError

    def generate_message_upload_path(self, realm_id: str, uploaded_file_name: str) -> str:
        raise NotImplementedError

    def upload_message_attachment(
        self,
        uploaded_file_name: str,
        uploaded_file_size: int,
        content_type: Optional[str],
        file_data: bytes,
        user_profile: UserProfile,
        target_realm: Optional[Realm] = None,
    ) -> str:
        raise NotImplementedError

    def save_attachment_contents(self, path_id: str, filehandle: BinaryIO) -> None:
        raise NotImplementedError

    def delete_message_attachment(self, path_id: str) -> bool:
        raise NotImplementedError

    def delete_message_attachments(self, path_ids: List[str]) -> None:
        for path_id in path_ids:
            self.delete_message_attachment(path_id)

    def all_message_attachments(self) -> Iterator[Tuple[str, datetime]]:
        raise NotImplementedError

    # Avatar image uploads
    def get_avatar_url(self, hash_key: str, medium: bool = False) -> str:
        raise NotImplementedError

    def upload_avatar_image(
        self,
        user_file: IO[bytes],
        acting_user_profile: UserProfile,
        target_user_profile: UserProfile,
        content_type: Optional[str] = None,
    ) -> None:
        raise NotImplementedError

    def copy_avatar(self, source_profile: UserProfile, target_profile: UserProfile) -> None:
        raise NotImplementedError

    def ensure_avatar_image(self, user_profile: UserProfile, is_medium: bool = False) -> None:
        raise NotImplementedError

    def delete_avatar_image(self, user: UserProfile) -> None:
        raise NotImplementedError

    # Realm icon and logo uploads
    def realm_avatar_and_logo_path(self, realm: Realm) -> str:
        return os.path.join(str(realm.id), "realm")

    def get_realm_icon_url(self, realm_id: int, version: int) -> str:
        raise NotImplementedError

    def upload_realm_icon_image(self, icon_file: IO[bytes], user_profile: UserProfile) -> None:
        raise NotImplementedError

    def get_realm_logo_url(self, realm_id: int, version: int, night: bool) -> str:
        raise NotImplementedError

    def upload_realm_logo_image(
        self, logo_file: IO[bytes], user_profile: UserProfile, night: bool
    ) -> None:
        raise NotImplementedError

    # Realm emoji uploads
    def get_emoji_url(self, emoji_file_name: str, realm_id: int, still: bool = False) -> str:
        raise NotImplementedError

    def upload_emoji_image(
        self, emoji_file: IO[bytes], emoji_file_name: str, user_profile: UserProfile
    ) -> bool:
        raise NotImplementedError

    # Export tarballs
    def get_export_tarball_url(self, realm: Realm, export_path: str) -> str:
        raise NotImplementedError

    def upload_export_tarball(
        self,
        realm: Realm,
        tarball_path: str,
        percent_callback: Optional[Callable[[Any], None]] = None,
    ) -> str:
        raise NotImplementedError

    def delete_export_tarball(self, export_path: str) -> Optional[str]:
        raise NotImplementedError


def create_attachment(
    file_name: str, path_id: str, user_profile: UserProfile, realm: Realm, file_size: int
) -> None:
    assert (user_profile.realm_id == realm.id) or is_cross_realm_bot_email(
        user_profile.delivery_email
    )
    attachment = Attachment.objects.create(
        file_name=file_name,
        path_id=path_id,
        owner=user_profile,
        realm=realm,
        size=file_size,
    )
    from zerver.actions.uploads import notify_attachment_update

    notify_attachment_update(user_profile, "add", attachment.to_dict())

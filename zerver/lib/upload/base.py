import io
import os
import re
import unicodedata
from datetime import datetime
from typing import IO, Any, BinaryIO, Callable, Iterator, List, Optional, Tuple

from django.utils.translation import gettext as _
from PIL import GifImagePlugin, Image, ImageOps, PngImagePlugin
from PIL.Image import DecompressionBombError

from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.models import Attachment, Realm, UserProfile, is_cross_realm_bot_email

DEFAULT_AVATAR_SIZE = 100
MEDIUM_AVATAR_SIZE = 500
DEFAULT_EMOJI_SIZE = 64

# These sizes were selected based on looking at the maximum common
# sizes in a library of animated custom emoji, balanced against the
# network cost of very large emoji images.
MAX_EMOJI_GIF_SIZE = 128
MAX_EMOJI_GIF_FILE_SIZE_BYTES = 128 * 1024 * 1024  # 128 kb


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


class BadImageError(JsonableError):
    code = ErrorCode.BAD_IMAGE


def resize_avatar(image_data: bytes, size: int = DEFAULT_AVATAR_SIZE) -> bytes:
    try:
        im = Image.open(io.BytesIO(image_data))
        im = ImageOps.exif_transpose(im)
        im = ImageOps.fit(im, (size, size), Image.Resampling.LANCZOS)
    except OSError:
        raise BadImageError(_("Could not decode image; did you upload an image file?"))
    except DecompressionBombError:
        raise BadImageError(_("Image size exceeds limit."))
    out = io.BytesIO()
    if im.mode == "CMYK":
        im = im.convert("RGB")
    im.save(out, format="png")
    return out.getvalue()


def resize_logo(image_data: bytes) -> bytes:
    try:
        im = Image.open(io.BytesIO(image_data))
        im = ImageOps.exif_transpose(im)
        im.thumbnail((8 * DEFAULT_AVATAR_SIZE, DEFAULT_AVATAR_SIZE), Image.Resampling.LANCZOS)
    except OSError:
        raise BadImageError(_("Could not decode image; did you upload an image file?"))
    except DecompressionBombError:
        raise BadImageError(_("Image size exceeds limit."))
    out = io.BytesIO()
    if im.mode == "CMYK":
        im = im.convert("RGB")
    im.save(out, format="png")
    return out.getvalue()


def resize_animated(im: Image.Image, size: int = DEFAULT_EMOJI_SIZE) -> bytes:
    assert im.n_frames > 1
    frames = []
    duration_info = []
    disposals = []
    # If 'loop' info is not set then loop for infinite number of times.
    loop = im.info.get("loop", 0)
    for frame_num in range(im.n_frames):
        im.seek(frame_num)
        new_frame = im.copy()
        new_frame.paste(im, (0, 0), im.convert("RGBA"))
        new_frame = ImageOps.pad(new_frame, (size, size), Image.Resampling.LANCZOS)
        frames.append(new_frame)
        if im.info.get("duration") is None:  # nocoverage
            raise BadImageError(_("Corrupt animated image."))
        duration_info.append(im.info["duration"])
        if isinstance(im, GifImagePlugin.GifImageFile):
            disposals.append(
                im.disposal_method  # type: ignore[attr-defined]  # private member missing from stubs
            )
        elif isinstance(im, PngImagePlugin.PngImageFile):
            disposals.append(im.info.get("disposal", PngImagePlugin.Disposal.OP_NONE))
        else:  # nocoverage
            raise BadImageError(_("Unknown animated image format."))
    out = io.BytesIO()
    frames[0].save(
        out,
        save_all=True,
        optimize=False,
        format=im.format,
        append_images=frames[1:],
        duration=duration_info,
        disposal=disposals,
        loop=loop,
    )

    return out.getvalue()


def resize_emoji(
    image_data: bytes, size: int = DEFAULT_EMOJI_SIZE
) -> Tuple[bytes, bool, Optional[bytes]]:
    # This function returns three values:
    # 1) Emoji image data.
    # 2) If emoji is gif i.e animated.
    # 3) If is animated then return still image data i.e first frame of gif.

    try:
        im = Image.open(io.BytesIO(image_data))
        image_format = im.format
        if getattr(im, "n_frames", 1) > 1:
            # There are a number of bugs in Pillow which cause results
            # in resized images being broken. To work around this we
            # only resize under certain conditions to minimize the
            # chance of creating ugly images.
            should_resize = (
                im.size[0] != im.size[1]  # not square
                or im.size[0] > MAX_EMOJI_GIF_SIZE  # dimensions too large
                or len(image_data) > MAX_EMOJI_GIF_FILE_SIZE_BYTES  # filesize too large
            )

            # Generate a still image from the first frame.  Since
            # we're converting the format to PNG anyway, we resize unconditionally.
            still_image = im.copy()
            still_image.seek(0)
            still_image = ImageOps.exif_transpose(still_image)
            still_image = ImageOps.fit(still_image, (size, size), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            still_image.save(out, format="PNG")
            still_image_data = out.getvalue()

            if should_resize:
                image_data = resize_animated(im, size)

            return image_data, True, still_image_data
        else:
            # Note that this is essentially duplicated in the
            # still_image code path, above.
            im = ImageOps.exif_transpose(im)
            im = ImageOps.fit(im, (size, size), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            im.save(out, format=image_format)
            return out.getvalue(), False, None
    except OSError:
        raise BadImageError(_("Could not decode image; did you upload an image file?"))
    except DecompressionBombError:
        raise BadImageError(_("Image size exceeds limit."))


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

import io
from typing import Optional, Tuple
from urllib.parse import urljoin

from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from PIL import GifImagePlugin, Image, ImageOps, PngImagePlugin
from PIL.Image import DecompressionBombError

from zerver.lib.camo import get_camo_url
from zerver.lib.exceptions import ErrorCode, JsonableError

DEFAULT_AVATAR_SIZE = 100
MEDIUM_AVATAR_SIZE = 500
DEFAULT_EMOJI_SIZE = 64

# These sizes were selected based on looking at the maximum common
# sizes in a library of animated custom emoji, balanced against the
# network cost of very large emoji images.
MAX_EMOJI_GIF_SIZE = 128
MAX_EMOJI_GIF_FILE_SIZE_BYTES = 128 * 1024 * 1024  # 128 kb


class BadImageError(JsonableError):
    code = ErrorCode.BAD_IMAGE


def user_uploads_or_external(url: str) -> bool:
    return not url_has_allowed_host_and_scheme(url, allowed_hosts=None) or url.startswith(
        "/user_uploads/"
    )


def generate_thumbnail_url(path: str, size: str = "0x0") -> str:
    path = urljoin("/", path)

    if url_has_allowed_host_and_scheme(path, allowed_hosts=None):
        return path
    return get_camo_url(path)


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
    # 2) If emoji is gif i.e. animated.
    # 3) If is animated then return still image data i.e. first frame of gif.

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

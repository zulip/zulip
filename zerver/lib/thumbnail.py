import logging
import os
from contextlib import contextmanager
from typing import Iterator, Optional, Tuple
from urllib.parse import urljoin

import pyvips
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _

from zerver.lib.camo import get_camo_url
from zerver.lib.exceptions import ErrorCode, JsonableError

DEFAULT_AVATAR_SIZE = 100
MEDIUM_AVATAR_SIZE = 500
DEFAULT_EMOJI_SIZE = 64

# We refuse to deal with any image whose total pixelcount exceeds this.
IMAGE_BOMB_TOTAL_PIXELS = 90000000

# Reject emoji which, after resizing, have stills larger than this
MAX_EMOJI_GIF_FILE_SIZE_BYTES = 128 * 1024  # 128 kb


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


@contextmanager
def libvips_check_image(image_data: bytes) -> Iterator[pyvips.Image]:
    # The primary goal of this is to verify that the image is valid,
    # and raise BadImageError otherwise.  The yielded `source_image`
    # may be ignored, since calling `thumbnail_buffer` is faster than
    # calling `thumbnail_image` on a pyvips.Image, since the latter
    # cannot make use of shrink-on-load optimizations:
    # https://www.libvips.org/API/current/libvips-resample.html#vips-thumbnail-image
    try:
        source_image = pyvips.Image.new_from_buffer(image_data, "")
    except pyvips.Error:
        raise BadImageError(_("Could not decode image; did you upload an image file?"))

    if source_image.width * source_image.height > IMAGE_BOMB_TOTAL_PIXELS:
        raise BadImageError(_("Image size exceeds limit."))

    try:
        yield source_image
    except pyvips.Error as e:  # nocoverage
        logging.exception(e)
        raise BadImageError(_("Bad image!"))


def resize_avatar(image_data: bytes, size: int = DEFAULT_AVATAR_SIZE) -> bytes:
    # This will scale up, if necessary, and will scale the smallest
    # dimension to fit.  That is, a 1x1000 image will end up with the
    # one middle pixel enlarged to fill the full square.
    with libvips_check_image(image_data):
        return pyvips.Image.thumbnail_buffer(
            image_data,
            size,
            height=size,
            crop=pyvips.Interesting.CENTRE,
        ).write_to_buffer(".png")


def resize_logo(image_data: bytes) -> bytes:
    # This will only scale the image down, and will resize it to
    # preserve aspect ratio and be contained within 8*AVATAR by AVATAR
    # pixels; it does not add any padding to make it exactly that
    # size.  A 1000x10 pixel image will end up as 800x8; a 10x10 will
    # end up 10x10.
    with libvips_check_image(image_data):
        return pyvips.Image.thumbnail_buffer(
            image_data,
            8 * DEFAULT_AVATAR_SIZE,
            height=DEFAULT_AVATAR_SIZE,
            size=pyvips.Size.DOWN,
        ).write_to_buffer(".png")


def resize_emoji(
    image_data: bytes, emoji_file_name: str, size: int = DEFAULT_EMOJI_SIZE
) -> Tuple[bytes, Optional[bytes]]:
    if len(image_data) > MAX_EMOJI_GIF_FILE_SIZE_BYTES:
        raise BadImageError(_("Image size exceeds limit."))

    # Square brackets are used for providing options to libvips' save
    # operation; these should have been filtered out earlier, so we
    # assert none are found here, for safety.
    write_file_ext = os.path.splitext(emoji_file_name)[1]
    assert "[" not in write_file_ext

    # This function returns two values:
    # 1) Emoji image data.
    # 2) If it is animated, the still image data i.e. first frame of gif.
    with libvips_check_image(image_data) as source_image:
        if source_image.get_n_pages() == 1:
            return (
                pyvips.Image.thumbnail_buffer(
                    image_data,
                    size,
                    height=size,
                    crop=pyvips.Interesting.CENTRE,
                ).write_to_buffer(write_file_ext),
                None,
            )
        first_still = pyvips.Image.thumbnail_buffer(
            image_data,
            size,
            height=size,
            crop=pyvips.Interesting.CENTRE,
        ).write_to_buffer(".png")

        animated = pyvips.Image.thumbnail_buffer(
            image_data,
            size,
            height=size,
            # This is passed to the loader, and means "load all
            # frames", instead of the default of just the first
            option_string="n=-1",
        )
        if animated.width != animated.get("page-height"):
            # If the image is non-square, we have to iterate the
            # frames to add padding to make it so
            if not animated.hasalpha():
                animated = animated.addalpha()
            frames = [
                frame.gravity(
                    pyvips.CompassDirection.CENTRE,
                    size,
                    size,
                    extend=pyvips.Extend.BACKGROUND,
                    background=[0, 0, 0, 0],
                )
                for frame in animated.pagesplit()
            ]
            animated = frames[0].pagejoin(frames[1:])
        return (animated.write_to_buffer(write_file_ext), first_still)

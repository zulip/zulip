import logging
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import pyvips
from bs4 import BeautifulSoup
from bs4.formatter import EntitySubstitution, HTMLFormatter
from django.utils.translation import gettext as _
from typing_extensions import Self, override

from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.mime_types import AUDIO_INLINE_MIME_TYPES, INLINE_MIME_TYPES
from zerver.lib.queue import queue_event_on_commit
from zerver.models import Attachment, ImageAttachment

DEFAULT_AVATAR_SIZE = 100
MEDIUM_AVATAR_SIZE = 500
DEFAULT_EMOJI_SIZE = 64

# We refuse to deal with any image whose total pixelcount exceeds
# this.  This is chosen to be around a quarter of a gigabyte for a
# 24-bit (3bpp) image.
IMAGE_BOMB_TOTAL_PIXELS = 90000000
IMAGE_MAX_ANIMATED_PIXELS = IMAGE_BOMB_TOTAL_PIXELS / 3

# Reject emoji which, after resizing, have stills larger than this
MAX_EMOJI_GIF_FILE_SIZE_BYTES = 128 * 1024  # 128 kb


@dataclass(frozen=True)
class BaseThumbnailFormat:  # noqa: PLW1641
    extension: str
    max_width: int
    max_height: int
    animated: bool

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseThumbnailFormat):
            return False
        return str(self) == str(other)

    @override
    def __str__(self) -> str:
        animated = "-anim" if self.animated else ""
        return f"{self.max_width}x{self.max_height}{animated}.{self.extension}"

    @classmethod
    def from_string(cls, format_string: str) -> Self | None:
        format_parts = re.match(r"(\d+)x(\d+)(-anim)?\.(\w+)$", format_string)
        if format_parts is None:
            return None

        return cls(
            max_width=int(format_parts[1]),
            max_height=int(format_parts[2]),
            animated=format_parts[3] is not None,
            extension=format_parts[4],
        )


@dataclass(frozen=True, eq=False)
class ThumbnailFormat(BaseThumbnailFormat):
    opts: str | None = ""


# Note that this is serialized into a JSONB column in the database,
# and as such fields cannot be removed without a migration.
@dataclass(frozen=True, eq=False)
class StoredThumbnailFormat(BaseThumbnailFormat):
    content_type: str
    width: int
    height: int
    byte_size: int


# Formats that we generate; the first animated and non-animated
# options on this list are the ones which are written into
# rendered_content.
THUMBNAIL_OUTPUT_FORMATS = (
    # We generate relatively large default "thumbnails", so that
    # clients that do not understand the thumbnailing protocol
    # (e.g. mobile) get something which does not look pixelated.  This
    # is also useful when the web client lightbox temporarily shows an
    # upsized thumbnail while loading the full resolution image.
    ThumbnailFormat("webp", 840, 560, animated=True),
    ThumbnailFormat("webp", 840, 560, animated=False),
)

# This format is generated, in addition to THUMBNAIL_OUTPUT_FORMATS,
# for images in THUMBNAIL_ACCEPT_IMAGE_TYPES which are not in
# INLINE_MIME_TYPES: somewhat-common image types which are not broadly
# supported by browsers.
TRANSCODED_IMAGE_FORMAT = ThumbnailFormat("webp", 4032, 3024, animated=False)


# These are the image content-types which the server supports parsing
# and thumbnailing; these do not need to supported on all browsers,
# since we will the serving thumbnailed versions of them.  Note that
# this does not provide any *security*, since the content-type is
# provided by the browser, and may not match the bytes they uploaded.
#
# This should be kept synced with the client-side image-picker in
# web/upload_widget.ts.  Any additions below must be accompanied by
# changes to the pyvips block below as well.
THUMBNAIL_ACCEPT_IMAGE_TYPES = frozenset(
    [
        "image/avif",
        "image/gif",
        "image/heic",
        "image/jpeg",
        "image/png",
        "image/tiff",
        "image/webp",
    ]
)

# This is what enforces security limitations on which formats are
# parsed; we disable all loaders, then re-enable the ones we support
# -- then explicitly disable any "untrusted" ones, in case libvips for
# some reason marks one of the above formats as such (because they are
# no longer fuzzed, for instance).
#
# Note that only libvips >= 8.13 (Ubuntu 24.04 or later, Debian 12 or
# later) supports this!  These are no-ops on earlier versions of libvips.
pyvips.operation_block_set("VipsForeignLoad", True)
pyvips.operation_block_set("VipsForeignLoadHeif", False)  # image/avif, image/heic
pyvips.operation_block_set("VipsForeignLoadNsgif", False)  # image/gif
pyvips.operation_block_set("VipsForeignLoadJpeg", False)  # image/jpeg
pyvips.operation_block_set("VipsForeignLoadPng", False)  # image/png
pyvips.operation_block_set("VipsForeignLoadTiff", False)  # image/tiff
pyvips.operation_block_set("VipsForeignLoadWebp", False)  # image/webp
pyvips.block_untrusted_set(True)

# Disable the operations cache; our only use here is thumbnail_buffer,
# which does not make use of it.
pyvips.voperation.cache_set_max(0)


class BadImageError(JsonableError):
    code = ErrorCode.BAD_IMAGE


@contextmanager
def libvips_check_image(
    image_data: bytes | pyvips.Source, truncated_animation: bool = False
) -> Iterator[pyvips.Image]:
    # The primary goal of this is to verify that the image is valid,
    # and raise BadImageError otherwise.  The yielded `source_image`
    # may be ignored, since calling `thumbnail_buffer` is faster than
    # calling `thumbnail_image` on a pyvips.Image, since the latter
    # cannot make use of shrink-on-load optimizations:
    # https://www.libvips.org/API/current/libvips-resample.html#vips-thumbnail-image
    try:
        if isinstance(image_data, bytes):
            source_image = pyvips.Image.new_from_buffer(image_data, "")
        else:
            source_image = pyvips.Image.new_from_source(image_data, "", access="sequential")
    except pyvips.Error:
        raise BadImageError(_("Could not decode image; did you upload an image file?"))

    if not truncated_animation:
        # For places where we do not truncate animations (e.g. emoji,
        # where the original is never served to clients, so we must
        # preserve the full animation) we count total pixels across
        # all frames for the limit.
        if (
            source_image.width * source_image.height * source_image.get_n_pages()
            > IMAGE_BOMB_TOTAL_PIXELS
        ):
            raise BadImageError(_("Image size exceeds limit."))
    else:
        # When thumbnailing image uploads, we truncate thumbnailed
        # animations, so we have different checks for animated vs
        # still images.
        if source_image.get_n_pages() == 1:
            if source_image.width * source_image.height > IMAGE_BOMB_TOTAL_PIXELS:
                raise BadImageError(_("Image size exceeds limit."))

        else:
            # For animated images, we have an additional limit -- we
            # want to be able to render at least 3 frames, and spend
            # no more than 1/3 of that IMAGE_BOMB_TOTAL_PIXELS budget
            # in doing so.
            if (
                source_image.width * source_image.height * min(3, source_image.get_n_pages())
                > IMAGE_MAX_ANIMATED_PIXELS
            ):
                raise BadImageError(_("Image size exceeds limit."))

    try:
        yield source_image
    except pyvips.Error as e:  # nocoverage
        logging.exception(e)
        raise BadImageError(_("Image is corrupted or truncated"))


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


def resize_realm_icon(image_data: bytes) -> bytes:
    return resize_avatar(image_data)


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
) -> tuple[bytes, bytes | None]:
    # Square brackets are used for providing options to libvips' save
    # operation; the extension on the filename comes from reversing
    # the content-type, which removes most of the attacker control of
    # this string, but assert it has no bracketed pieces for safety.
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


def missing_thumbnails(
    image_attachment: ImageAttachment,
) -> list[ThumbnailFormat]:
    seen_thumbnails: set[StoredThumbnailFormat] = set()
    for existing_thumbnail in image_attachment.thumbnail_metadata:
        seen_thumbnails.add(StoredThumbnailFormat(**existing_thumbnail))

    potential_output_formats = list(THUMBNAIL_OUTPUT_FORMATS)
    if image_attachment.content_type not in INLINE_MIME_TYPES:
        if image_attachment.original_width_px >= image_attachment.original_height_px:
            additional_format = ThumbnailFormat(
                TRANSCODED_IMAGE_FORMAT.extension,
                TRANSCODED_IMAGE_FORMAT.max_width,
                TRANSCODED_IMAGE_FORMAT.max_height,
                TRANSCODED_IMAGE_FORMAT.animated,
            )
        else:
            additional_format = ThumbnailFormat(
                TRANSCODED_IMAGE_FORMAT.extension,
                # Swap width and height to make a portrait-oriented version
                TRANSCODED_IMAGE_FORMAT.max_height,
                TRANSCODED_IMAGE_FORMAT.max_width,
                TRANSCODED_IMAGE_FORMAT.animated,
            )
        potential_output_formats.append(additional_format)

    # We use the shared `__eq__` method from BaseThumbnailFormat to
    # compare between the StoredThumbnailFormat values pulled from the
    # database, and the ThumbnailFormat values in
    # THUMBNAIL_OUTPUT_FORMATS.
    needed_thumbnails = [
        thumbnail_format
        for thumbnail_format in potential_output_formats
        if thumbnail_format not in seen_thumbnails
    ]

    if image_attachment.frames == 1:
        # We do not generate -anim versions if the source is still
        needed_thumbnails = [
            thumbnail_format
            for thumbnail_format in needed_thumbnails
            if not thumbnail_format.animated
        ]

    return needed_thumbnails


def maybe_thumbnail(
    content: bytes | pyvips.Source,
    content_type: str | None,
    path_id: str,
    realm_id: int,
    skip_events: bool = False,
) -> ImageAttachment | None:
    if content_type not in THUMBNAIL_ACCEPT_IMAGE_TYPES:
        # If it doesn't self-report as an image file that we might want
        # to thumbnail, don't parse the bytes at all.
        return None
    try:
        # This only attempts to read the header, not the full image content
        with libvips_check_image(content, truncated_animation=True) as image:
            # "original_width_px" and "original_height_px" here are
            # _as rendered_, after applying the orientation
            # information which the image may contain.
            if (
                "orientation" in image.get_fields()
                and image.get("orientation") >= 5
                and image.get("orientation") <= 8
            ):
                (width, height) = (image.height, image.width)
            else:
                (width, height) = (image.width, image.height)

            image_row = ImageAttachment.objects.create(
                realm_id=realm_id,
                path_id=path_id,
                original_width_px=width,
                original_height_px=height,
                frames=image.get_n_pages(),
                thumbnail_metadata=[],
                content_type=content_type,
            )
            if not skip_events:
                # The only reason to skip sending thumbnail events is
                # during import, when the events are separately
                # enqueued during message rendering; thumbnailing them
                # before/during message rendering can cause race
                # conditions.
                queue_event_on_commit("thumbnail", {"id": image_row.id})
            return image_row
    except BadImageError:
        return None


def get_image_thumbnail_path(
    image_attachment: ImageAttachment,
    thumbnail_format: BaseThumbnailFormat,
) -> str:
    return f"thumbnail/{image_attachment.path_id}/{thumbnail_format!s}"


def split_thumbnail_path(file_path: str) -> tuple[str, BaseThumbnailFormat]:
    assert file_path.startswith("thumbnail/")
    path_parts = file_path.split("/")
    thumbnail_format = BaseThumbnailFormat.from_string(path_parts.pop())
    assert thumbnail_format is not None
    path_id = "/".join(path_parts[1:])
    return path_id, thumbnail_format


@dataclass
class MarkdownImageMetadata:
    url: str | None
    is_animated: bool
    original_width_px: int
    original_height_px: int
    original_content_type: str | None
    transcoded_image: StoredThumbnailFormat | None = None


@dataclass
class AttachmentData:
    audio_path_ids: set[str]
    image_metadata: dict[str, MarkdownImageMetadata]


def get_user_upload_previews(
    realm_id: int,
    content: str,
    lock: bool = False,
    enqueue: bool = True,
    path_ids: list[str] | None = None,
) -> AttachmentData:
    if path_ids is None:
        path_ids = re.findall(r"/user_uploads/(\d+/[/\w.-]+)", content)
    if not path_ids:
        return AttachmentData(
            audio_path_ids=set(),
            image_metadata={},
        )

    image_metadata: dict[str, MarkdownImageMetadata] = {}

    image_attachments = ImageAttachment.objects.filter(
        realm_id=realm_id, path_id__in=path_ids
    ).order_by("id")
    if lock:
        image_attachments = image_attachments.select_for_update(of=("self",))
    for image_attachment in image_attachments:
        if image_attachment.thumbnail_metadata == []:
            # Image exists, and header of it parsed as a valid image,
            # but has not been thumbnailed yet; we will render a
            # spinner.
            image_metadata[image_attachment.path_id] = MarkdownImageMetadata(
                url=None,
                is_animated=False,
                original_width_px=image_attachment.original_width_px,
                original_height_px=image_attachment.original_height_px,
                original_content_type=image_attachment.content_type,
            )

            # We re-queue the row for thumbnailing to make sure that
            # we do eventually thumbnail it (e.g. if this is a
            # historical upload from before this system, which we
            # backfilled ImageAttachment rows for); this is a no-op in
            # the worker if all of the currently-configured thumbnail
            # formats have already been generated.
            if enqueue:
                queue_event_on_commit("thumbnail", {"id": image_attachment.id})
        else:
            url, is_animated = get_default_thumbnail_url(image_attachment)
            image_metadata[image_attachment.path_id] = MarkdownImageMetadata(
                url=url,
                is_animated=is_animated,
                original_width_px=image_attachment.original_width_px,
                original_height_px=image_attachment.original_height_px,
                original_content_type=image_attachment.content_type,
                transcoded_image=get_transcoded_format(image_attachment),
            )

    non_image_path_ids = [path_id for path_id in path_ids if image_metadata.get(path_id) is None]
    non_image_attachments = Attachment.objects.filter(
        realm_id=realm_id, path_id__in=non_image_path_ids
    ).order_by("id")
    audio_path_ids = {
        attachment.path_id
        for attachment in non_image_attachments
        if attachment.content_type in AUDIO_INLINE_MIME_TYPES
    }

    return AttachmentData(
        audio_path_ids=audio_path_ids,
        image_metadata=image_metadata,
    )


def get_default_thumbnail_url(image_attachment: ImageAttachment) -> tuple[str, bool]:
    # For "dumb" clients which cannot rewrite it into their
    # preferred format and size, we choose the first one in
    # THUMBNAIL_OUTPUT_FORMATS which matches the animated/not
    # nature of the source image.
    found_format: ThumbnailFormat | None = None
    for thumbnail_format in THUMBNAIL_OUTPUT_FORMATS:
        if thumbnail_format.animated == (image_attachment.frames > 1):
            found_format = thumbnail_format
            break
    if found_format is None:
        # No animated thumbnail formats exist somehow, and the
        # image is animated?  Just take the first thumbnail
        # format.
        found_format = THUMBNAIL_OUTPUT_FORMATS[0]
    return (
        "/user_uploads/" + get_image_thumbnail_path(image_attachment, found_format),
        found_format.animated,
    )


def get_transcoded_format(
    image_attachment: ImageAttachment,
) -> StoredThumbnailFormat | None:
    # Returns None if the original content-type is judged to be
    # renderable inline.  Otherwise, we return the largest thumbnail
    # that we generated.  Since formats which are thumbnailable but
    # not in INLINE_MIME_TYPES get an extra large-resolution thumbnail
    # added to their list of formats, this is thus either None or a
    # high-resolution thumbnail.
    if image_attachment.content_type is None or image_attachment.content_type in INLINE_MIME_TYPES:
        return None

    thumbs_by_size = sorted(
        (StoredThumbnailFormat(**d) for d in image_attachment.thumbnail_metadata),
        key=lambda t: t.width * t.height,
    )
    return thumbs_by_size.pop() if thumbs_by_size else None


# Like HTMLFormatter.REGISTRY["html5"], this formatter avoids producing
# self-closing tags, but it differs by avoiding unnecessary escaping with
# HTML5-specific entities that cannot be parsed by lxml and libxml2
# (https://bugs.launchpad.net/lxml/+bug/2031045).
html_formatter = HTMLFormatter(
    entity_substitution=EntitySubstitution.substitute_xml,  # not substitute_html
    void_element_close_prefix="",
    empty_attributes_are_booleans=True,
)


def rewrite_thumbnailed_images(
    rendered_content: str,
    images: dict[str, MarkdownImageMetadata],
    to_delete: set[str] | None = None,
) -> tuple[str | None, set[str]]:
    if not images and not to_delete:
        return None, set()

    remaining_thumbnails = set()
    parsed_message = BeautifulSoup(rendered_content, "html.parser")

    changed = False
    for inline_image_div in parsed_message.find_all("div", class_="message_inline_image"):
        image_link = inline_image_div.find("a")
        if (
            image_link is None
            or image_link["href"] is None
            or not image_link["href"].startswith("/user_uploads/")
        ):
            # This is not an inline image generated by the markdown
            # processor for a locally-uploaded image.
            continue

        path_id = image_link["href"].removeprefix("/user_uploads/")
        image_data = images.get(path_id)

        image_tag = image_link.find("img", class_="image-loading-placeholder")
        if image_tag is None:
            image_tag = image_link.find("img", src=image_link["href"])
            if image_tag and image_data is not None:
                # The <img> element has the same src as the link,
                # which means this is an older, non-thumbnailed
                # version.  Let's replace the image with a spinner,
                # and mark it as a pending thumbnail.
                changed = True
                image_tag["src"] = "/static/images/loading/loader-black.svg"
                image_tag["class"] = "image-loading-placeholder"
                image_tag["data-original-dimensions"] = (
                    f"{image_data.original_width_px}x{image_data.original_height_px}"
                )
                if image_data.original_content_type:
                    image_tag["data-original-content-type"] = image_data.original_content_type
                remaining_thumbnails.add(path_id)
                continue
            else:
                # The placeholder was already replaced -- for instance,
                # this is expected if multiple images are included in the
                # same message.  The second time this is run, for the
                # second image, the first image will have no placeholder.
                continue

        if to_delete and path_id in to_delete:
            # This was not a valid thumbnail target, for some reason.
            # Trim out the whole "message_inline_image" element, since
            # it's not going be renderable by clients either.
            inline_image_div.decompose()
            changed = True
            continue

        if image_data is None:
            # The message has multiple images, and we're updating just
            # one image, and it's not this one.  Leave this one as-is.
            remaining_thumbnails.add(path_id)
        elif image_data.url is None:
            # We're re-rendering the whole message, so fetched all of
            # the image metadata rows; this is one of the images we
            # about, but is not thumbnailed yet.
            remaining_thumbnails.add(path_id)
        else:
            changed = True
            del image_tag["class"]
            image_tag["src"] = image_data.url
            image_tag["data-original-dimensions"] = (
                f"{image_data.original_width_px}x{image_data.original_height_px}"
            )
            image_tag["data-original-content-type"] = image_data.original_content_type
            if image_data.is_animated:
                image_tag["data-animated"] = "true"
            if image_data.transcoded_image is not None:
                image_tag["data-transcoded-image"] = str(image_data.transcoded_image)

    if changed:
        return (
            parsed_message.encode(formatter=html_formatter).decode().strip(),
            remaining_thumbnails,
        )
    else:
        return None, remaining_thumbnails

import logging
import time
from dataclasses import asdict, dataclass
from io import BytesIO
from typing import Any

import pyvips
from django.db import transaction
from typing_extensions import override

from zerver.actions.message_edit import do_update_embedded_data
from zerver.lib.mime_types import guess_type
from zerver.lib.thumbnail import (
    IMAGE_MAX_ANIMATED_PIXELS,
    MarkdownImageMetadata,
    StoredThumbnailFormat,
    get_default_thumbnail_url,
    get_image_thumbnail_path,
    get_transcoded_format,
    missing_thumbnails,
    rewrite_thumbnailed_images,
)
from zerver.lib.upload import save_attachment_contents, upload_backend
from zerver.models import ArchivedMessage, ImageAttachment, Message
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("thumbnail")
class ThumbnailWorker(QueueProcessingWorker):
    @override
    def consume(self, event: dict[str, Any]) -> None:
        start_time = time.perf_counter()
        with transaction.atomic(savepoint=False):
            try:
                # This lock prevents us from racing with the on-demand
                # rendering that can be triggered if a request is made
                # directly to a thumbnail URL we have not made yet.
                # This may mean that we may generate 0 thumbnail
                # images once we get the lock.
                row = ImageAttachment.objects.select_for_update(of=("self",)).get(id=event["id"])
            except ImageAttachment.DoesNotExist:  # nocoverage
                logger.info(
                    "ImageAttachment row %d missing [%dms]",
                    event["id"],
                    (time.perf_counter() - start_time) * 1000,
                )
                return
            lock_time = time.perf_counter() - start_time
            logger.info("Starting thumbnailing for %s", row.path_id)
            result = ensure_thumbnails(row)
            commit_time = time.perf_counter()
        end_time = time.perf_counter()
        logger.info(
            "Processed %d thumbnails [%dms; lock=%dms, fetch=%dms, thumb=%dms, upload=%dms, rewrite=%dms, commit=%dms]",
            result.generated_thumbnail_count,
            (end_time - start_time) * 1000,
            lock_time * 1000,
            result.fetching_seconds * 1000,
            result.processing_seconds * 1000,
            result.uploading_seconds * 1000,
            result.message_update_seconds * 1000,
            (end_time - commit_time) * 1000,
        )


@dataclass
class ThumbnailingResult:
    generated_thumbnail_count: int = 0
    fetching_seconds: float = 0
    processing_seconds: float = 0
    uploading_seconds: float = 0
    message_update_seconds: float = 0


def ensure_thumbnails(image_attachment: ImageAttachment) -> ThumbnailingResult:
    needed_thumbnails = missing_thumbnails(image_attachment)

    if not needed_thumbnails:
        return ThumbnailingResult()

    written_images = 0
    with BytesIO() as f:
        start_time = time.perf_counter()
        save_attachment_contents(image_attachment.path_id, f)
        image_bytes = f.getvalue()
        fetching_seconds = time.perf_counter() - start_time
    try:
        # TODO: We could save some computational time by using the same
        # bytes if multiple resolutions are larger than the source
        # image.  That is, if the input is 10x10, a 100x100.jpg is
        # going to be the same as a 200x200.jpg, since those set the
        # max dimensions, and we do not scale up.
        processing_seconds = 0.0
        uploading_seconds = 0.0
        for thumbnail_format in needed_thumbnails:
            # This will scale to fit within the given dimensions; it
            # may be smaller one one or more of them.
            logger.debug(
                "Resizing to %d x %d, from %d x %d",
                thumbnail_format.max_width,
                thumbnail_format.max_height,
                image_attachment.original_width_px,
                image_attachment.original_height_px,
            )
            load_opts = ""
            if image_attachment.frames > 1:
                # If the original has multiple frames, we want to load
                # one of them if we're outputting to a static format,
                # otherwise we load them all.
                if thumbnail_format.animated:
                    # We compute how many frames to thumbnail based on
                    # how many frames it will take us to get to
                    # IMAGE_MAX_ANIMATED_PIXELS
                    pixels_per_frame = (
                        image_attachment.original_width_px * image_attachment.original_height_px
                    )
                    if pixels_per_frame * image_attachment.frames < IMAGE_MAX_ANIMATED_PIXELS:
                        load_opts = "n=-1"
                    else:
                        load_opts = f"n={IMAGE_MAX_ANIMATED_PIXELS // pixels_per_frame}"
                else:
                    load_opts = "n=1"
            start_time = time.perf_counter()
            resized = pyvips.Image.thumbnail_buffer(
                image_bytes,
                thumbnail_format.max_width,
                height=thumbnail_format.max_height,
                option_string=load_opts,
                size=pyvips.Size.DOWN,
            )
            thumbnailed_bytes = resized.write_to_buffer(
                f".{thumbnail_format.extension}[{thumbnail_format.opts}]"
            )
            processing_seconds += time.perf_counter() - start_time
            content_type = guess_type(f"image.{thumbnail_format.extension}")[0]
            assert content_type is not None
            thumbnail_path = get_image_thumbnail_path(image_attachment, thumbnail_format)
            logger.debug("Uploading %d bytes to %s", len(thumbnailed_bytes), thumbnail_path)
            start_time = time.perf_counter()
            upload_backend.upload_message_attachment(
                thumbnail_path,
                str(thumbnail_format),
                content_type,
                thumbnailed_bytes,
                None,
                None,
            )
            uploading_seconds += time.perf_counter() - start_time
            height = resized.get("page-height") if thumbnail_format.animated else resized.height
            image_attachment.thumbnail_metadata.append(
                asdict(
                    StoredThumbnailFormat(
                        extension=thumbnail_format.extension,
                        content_type=content_type,
                        max_width=thumbnail_format.max_width,
                        max_height=thumbnail_format.max_height,
                        animated=thumbnail_format.animated,
                        width=resized.width,
                        height=height,
                        byte_size=len(thumbnailed_bytes),
                    )
                )
            )
            written_images += 1

    except pyvips.Error as e:
        logger.exception(
            "Failed to thumbnail %s, %d byte %s @ %dx%d: %s",
            image_attachment.path_id,
            len(image_bytes),
            image_attachment.content_type,
            image_attachment.original_width_px,
            image_attachment.original_height_px,
            e.message,
        )

        if written_images == 0 and len(image_attachment.thumbnail_metadata) == 0:
            # We have never thumbnailed this -- it most likely had
            # bad data.  Remove the ImageAttachment row, since it is
            # not valid for thumbnailing.
            start_time = time.perf_counter()
            update_message_rendered_content(
                image_attachment.realm_id, image_attachment.path_id, None
            )
            message_update_seconds = time.perf_counter() - start_time
            image_attachment.delete()
            return ThumbnailingResult(
                0, fetching_seconds, processing_seconds, uploading_seconds, message_update_seconds
            )
        else:  # nocoverage
            # TODO: Clean up any dangling thumbnails we may have
            # produced?  Seems unlikely that we'd fail on one size,
            # but not another, but anything's possible.
            pass

    image_attachment.save(update_fields=["thumbnail_metadata"])
    start_time = time.perf_counter()
    url, is_animated = get_default_thumbnail_url(image_attachment)
    update_message_rendered_content(
        image_attachment.realm_id,
        image_attachment.path_id,
        MarkdownImageMetadata(
            url=url,
            is_animated=is_animated,
            original_width_px=image_attachment.original_width_px,
            original_height_px=image_attachment.original_height_px,
            original_content_type=image_attachment.content_type,
            transcoded_image=get_transcoded_format(image_attachment),
        ),
    )
    message_update_seconds = time.perf_counter() - start_time
    return ThumbnailingResult(
        written_images,
        fetching_seconds,
        processing_seconds,
        uploading_seconds,
        message_update_seconds,
    )


def update_message_rendered_content(
    realm_id: int, path_id: str, image_data: MarkdownImageMetadata | None
) -> None:
    for message_class in (Message, ArchivedMessage):
        messages_with_image = (
            message_class.objects.filter(realm_id=realm_id, attachment__path_id=path_id)
            .select_for_update(of=("self",))
            .order_by("id")
        )
        for message in messages_with_image:
            assert message.rendered_content is not None
            rendered_content = rewrite_thumbnailed_images(
                message.rendered_content,
                {} if image_data is None else {path_id: image_data},
                {path_id} if image_data is None else set(),
            )[0]
            if rendered_content is None:
                # There were no updates -- for instance, if we re-run
                # ensure_thumbnails on an ImageAttachment we already
                # ran it on once.  Do not bother to no-op update
                # clients.
                continue
            if isinstance(message, Message):
                # Perform a silent update push to the clients
                do_update_embedded_data(message.sender, message, rendered_content)
            else:
                message.rendered_content = rendered_content
                message.save(update_fields=["rendered_content"])

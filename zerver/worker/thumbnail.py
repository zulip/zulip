import logging
import time
from dataclasses import asdict
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
        start = time.time()
        with transaction.atomic(savepoint=False):
            try:
                # This lock prevents us from racing with the on-demand
                # rendering that can be triggered if a request is made
                # directly to a thumbnail URL we have not made yet.
                # This may mean that we may generate 0 thumbnail
                # images once we get the lock.
                row = ImageAttachment.objects.select_for_update(of=("self",)).get(id=event["id"])
            except ImageAttachment.DoesNotExist:  # nocoverage
                logger.info("ImageAttachment row %d missing", event["id"])
                return
            uploaded_thumbnails = ensure_thumbnails(row)
        end = time.time()
        logger.info(
            "Processed %d thumbnails (%dms)",
            uploaded_thumbnails,
            (end - start) * 1000,
        )


def ensure_thumbnails(image_attachment: ImageAttachment) -> int:
    needed_thumbnails = missing_thumbnails(image_attachment)

    if not needed_thumbnails:
        return 0

    written_images = 0
    image_bytes = BytesIO()
    save_attachment_contents(image_attachment.path_id, image_bytes)
    try:
        # TODO: We could save some computational time by using the same
        # bytes if multiple resolutions are larger than the source
        # image.  That is, if the input is 10x10, a 100x100.jpg is
        # going to be the same as a 200x200.jpg, since those set the
        # max dimensions, and we do not scale up.
        for thumbnail_format in needed_thumbnails:
            # This will scale to fit within the given dimensions; it
            # may be smaller one one or more of them.
            logger.info(
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
            resized = pyvips.Image.thumbnail_buffer(
                image_bytes.getbuffer(),
                thumbnail_format.max_width,
                height=thumbnail_format.max_height,
                option_string=load_opts,
                size=pyvips.Size.DOWN,
            )
            thumbnailed_bytes = resized.write_to_buffer(
                f".{thumbnail_format.extension}[{thumbnail_format.opts}]"
            )
            content_type = guess_type(f"image.{thumbnail_format.extension}")[0]
            assert content_type is not None
            thumbnail_path = get_image_thumbnail_path(image_attachment, thumbnail_format)
            logger.info("Uploading %d bytes to %s", len(thumbnailed_bytes), thumbnail_path)
            upload_backend.upload_message_attachment(
                thumbnail_path,
                str(thumbnail_format),
                content_type,
                thumbnailed_bytes,
                None,
            )
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
        logger.exception(e)

        if written_images == 0 and len(image_attachment.thumbnail_metadata) == 0:
            # We have never thumbnailed this -- it most likely had
            # bad data.  Remove the ImageAttachment row, since it is
            # not valid for thumbnailing.
            update_message_rendered_content(
                image_attachment.realm_id, image_attachment.path_id, None
            )
            image_attachment.delete()
            return 0
        else:  # nocoverage
            # TODO: Clean up any dangling thumbnails we may have
            # produced?  Seems unlikely that we'd fail on one size,
            # but not another, but anything's possible.
            pass

    image_attachment.save(update_fields=["thumbnail_metadata"])
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
    return written_images


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

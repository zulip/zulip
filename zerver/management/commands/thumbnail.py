from datetime import timedelta
from typing import Any

from django.core.management.base import CommandParser
from django.db.models import Exists, OuterRef
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.message_edit import re_thumbnail
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.queue import queue_event_on_commit
from zerver.lib.thumbnail import StoredThumbnailFormat, get_image_thumbnail_path
from zerver.lib.upload import all_message_attachments
from zerver.models import ArchivedMessage, Attachment, ImageAttachment, Message


class Command(ZulipBaseCommand):
    help = """Manages thumbnailing in messages."""

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        self.add_realm_args(parser, required=True)
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument(
            "--stuck-spinners",
            action="store_true",
            help="Attempt to re-render messages with stuck spinners",
        )
        mode.add_argument(
            "--old-images",
            action="store_true",
            help="Generate thumbnails of old images",
        )
        mode.add_argument(
            "--missing-files",
            action="store_true",
            help="Regenerate thumbnails when their files are missing",
        )
        parser.add_argument(
            "--cutoff",
            help="Only process messages sent less than this many days ago",
            type=int,
            default=100,
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None

        if options.get("missing_files"):
            realm_imageattachments = (
                ImageAttachment.objects.alias(
                    in_realm=Exists(
                        Attachment.objects.filter(path_id=OuterRef("path_id"), realm_id=realm.id)
                    )
                )
                .filter(in_realm=True)
                .exclude(thumbnail_metadata=[])
            )
            for image_attachment in realm_imageattachments:
                found = []
                changed = False
                thumb_dir = f"thumbnail/{image_attachment.path_id}"
                found_thumbs = [
                    e[0] for e in all_message_attachments(include_thumbnails=True, prefix=thumb_dir)
                ]
                for existing_thumbnail in image_attachment.thumbnail_metadata:
                    thumb = StoredThumbnailFormat(**existing_thumbnail)
                    if get_image_thumbnail_path(image_attachment, thumb) in found_thumbs:
                        found.append(existing_thumbnail)
                    else:
                        changed = True
                if changed:
                    image_attachment.thumbnail_metadata = found
                    image_attachment.save(update_fields=["thumbnail_metadata"])
                    queue_event_on_commit("thumbnail", {"id": image_attachment.id})
            return

        for message_class in (Message, ArchivedMessage):
            messages = message_class.objects.filter(
                realm_id=realm.id,
                has_image=True,
                date_sent__gt=timezone_now() - timedelta(days=options["cutoff"]),
            )
            if options.get("stuck_spinners"):
                messages = messages.filter(
                    rendered_content__contains='class="image-loading-placeholder"',
                    date_sent__lt=timezone_now() - timedelta(seconds=60),
                )
            elif options.get("old_images"):
                messages = messages.filter(
                    rendered_content__contains='<img src="/user_uploads/',
                ).exclude(
                    rendered_content__contains='<img src="/user_uploads/thumbnail/',
                )

            message_ids = list(messages.values_list("id", flat=True))
            print(f"Processing {len(message_ids)} {message_class.__name__} objects")
            for i, message_id in enumerate(message_ids):
                re_thumbnail(message_class, message_id, enqueue=options["old_images"])

                if (i + 1) % 100 == 0:
                    print(f"Processed {i + 1}/{len(message_ids)} {message_class.__name__} objects")

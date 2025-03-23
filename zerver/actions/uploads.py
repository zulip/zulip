import logging
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet

from zerver.lib.attachments import validate_attachment_request
from zerver.lib.markdown import MessageRenderingResult
from zerver.lib.thumbnail import StoredThumbnailFormat, get_image_thumbnail_path
from zerver.lib.upload import claim_attachment, delete_message_attachments
from zerver.models import (
    ArchivedAttachment,
    Attachment,
    ImageAttachment,
    Message,
    ScheduledMessage,
    Stream,
    UserProfile,
)
from zerver.tornado.django_api import send_event_on_commit


@dataclass
class AttachmentChangeResult:
    did_attachment_change: bool
    detached_attachments: list[dict[str, Any]]


def notify_attachment_update(
    user_profile: UserProfile, op: str, attachment_dict: dict[str, Any]
) -> None:
    event = {
        "type": "attachment",
        "op": op,
        "attachment": attachment_dict,
        "upload_space_used": user_profile.realm.currently_used_upload_space_bytes(),
    }
    send_event_on_commit(user_profile.realm, event, [user_profile.id])


def do_claim_attachments(
    message: Message | ScheduledMessage, potential_path_ids: list[str]
) -> bool:
    claimed = False
    for path_id in potential_path_ids:
        user_profile = message.sender
        is_message_realm_public = False
        is_message_web_public = False
        if message.is_stream_message():
            stream = Stream.objects.get(id=message.recipient.type_id)
            is_message_realm_public = stream.is_public()
            is_message_web_public = stream.is_web_public

        if not validate_attachment_request(user_profile, path_id)[0]:
            # Technically, there are 2 cases here:
            # * The user put something in their message that has the form
            # of an upload URL, but does not actually correspond to a previously
            # uploaded file.  validate_attachment_request will return None.
            # * The user is trying to send a link to a file they don't have permission to
            # access themselves.  validate_attachment_request will return False.
            #
            # Either case is unusual and suggests a UI bug that got
            # the user in this situation, so we log in these cases.
            logging.warning(
                "User %s tried to share upload %s in message %s, but lacks permission",
                user_profile.id,
                path_id,
                message.id,
            )
            continue

        claimed = True
        attachment = claim_attachment(
            path_id, message, is_message_realm_public, is_message_web_public
        )
        if not isinstance(message, ScheduledMessage):
            # attachment update events don't say anything about scheduled messages,
            # so sending an event is pointless.
            notify_attachment_update(user_profile, "update", attachment.to_dict())
    return claimed


@transaction.atomic(durable=True)
def clear_old_unclaimed_attachments() -> None:
    """delete marked-as-deleted files (which were also deleted from storage) from db"""
    attachments_path_ids = Attachment.objects.filter(deleted=True).values_list("path_id", flat=True)
    archived_attachments_path_ids = ArchivedAttachment.objects.filter(deleted=True).values_list(
        "path_id", flat=True
    )
    ImageAttachment.objects.filter(
        Q(path_id__in=attachments_path_ids) | Q(path_id__in=archived_attachments_path_ids)
    ).delete()
    Attachment.objects.filter(deleted=True).delete()
    ArchivedAttachment.objects.filter(deleted=True).delete()


DELETE_BATCH_SIZE = 1000


def do_delete_old_unclaimed_attachments(
    old_unclaimed_attachments: QuerySet[Attachment],
    old_unclaimed_archived_attachments: QuerySet[ArchivedAttachment],
) -> None:
    with transaction.atomic(savepoint=False):
        old_unclaimed_attachments.update(deleted=True)
        old_unclaimed_archived_attachments.update(deleted=True)

    # An attachment may be removed from Attachments and
    # ArchiveAttachments in the same run; prevent warnings from the
    # backing store by only removing it from there once.
    already_removed = set()
    storage_paths = []
    for attachment in old_unclaimed_attachments:
        storage_paths.append(attachment.path_id)
        image_row = ImageAttachment.objects.filter(path_id=attachment.path_id).first()
        if not image_row:
            continue
        for existing_thumbnail in image_row.thumbnail_metadata:
            thumb = StoredThumbnailFormat(**existing_thumbnail)
            storage_paths.append(get_image_thumbnail_path(image_row, thumb))
        already_removed.add(attachment.path_id)

    for archived_attachment in old_unclaimed_archived_attachments:
        if archived_attachment.path_id not in already_removed:
            storage_paths.append(archived_attachment.path_id)
            image_row = ImageAttachment.objects.filter(path_id=archived_attachment.path_id).first()
            if not image_row:
                continue
            for existing_thumbnail in image_row.thumbnail_metadata:  # nocoverage
                thumb = StoredThumbnailFormat(**existing_thumbnail)
                storage_paths.append(get_image_thumbnail_path(image_row, thumb))

    # delete files from storage, deleting one DELETE_BATCH_SIZE at a time.
    for batch_start_index in range(0, len(storage_paths), DELETE_BATCH_SIZE):
        delete_message_attachments(
            storage_paths[batch_start_index : batch_start_index + DELETE_BATCH_SIZE]
        )

    clear_old_unclaimed_attachments()


def check_attachment_reference_change(
    message: Message | ScheduledMessage, rendering_result: MessageRenderingResult
) -> AttachmentChangeResult:
    # For a unsaved message edit (message.* has been updated, but not
    # saved to the database), adjusts Attachment data to correspond to
    # the new content.
    prev_attachments = {a.path_id for a in message.attachment_set.all()}
    new_attachments = set(rendering_result.potential_attachment_path_ids)

    if new_attachments == prev_attachments:
        return AttachmentChangeResult(bool(prev_attachments), [])

    to_remove = list(prev_attachments - new_attachments)
    if len(to_remove) > 0:
        attachments_to_update = Attachment.objects.filter(path_id__in=to_remove).select_for_update()
        message.attachment_set.remove(*attachments_to_update)

    sender = message.sender
    detached_attachments_query = Attachment.objects.filter(
        path_id__in=to_remove, messages__isnull=True, owner=sender
    )
    detached_attachments = [attachment.to_dict() for attachment in detached_attachments_query]

    to_add = list(new_attachments - prev_attachments)
    if len(to_add) > 0:
        do_claim_attachments(message, to_add)

    return AttachmentChangeResult(message.attachment_set.exists(), detached_attachments)

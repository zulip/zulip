import logging
from typing import Any, Dict, List, Union

from zerver.lib.markdown import MessageRenderingResult
from zerver.lib.upload import claim_attachment, delete_message_attachment
from zerver.models import (
    Attachment,
    Message,
    ScheduledMessage,
    Stream,
    UserProfile,
    get_old_unclaimed_attachments,
    validate_attachment_request,
)
from zerver.tornado.django_api import send_event


def notify_attachment_update(
    user_profile: UserProfile, op: str, attachment_dict: Dict[str, Any]
) -> None:
    event = {
        "type": "attachment",
        "op": op,
        "attachment": attachment_dict,
        "upload_space_used": user_profile.realm.currently_used_upload_space_bytes(),
    }
    send_event(user_profile.realm, event, [user_profile.id])


def do_claim_attachments(
    message: Union[Message, ScheduledMessage], potential_path_ids: List[str]
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

        if not validate_attachment_request(user_profile, path_id):
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
            user_profile, path_id, message, is_message_realm_public, is_message_web_public
        )
        if not isinstance(message, ScheduledMessage):
            # attachment update events don't say anything about scheduled messages,
            # so sending an event is pointless.
            notify_attachment_update(user_profile, "update", attachment.to_dict())
    return claimed


def do_delete_old_unclaimed_attachments(weeks_ago: int) -> None:
    old_unclaimed_attachments, old_unclaimed_archived_attachments = get_old_unclaimed_attachments(
        weeks_ago
    )

    # An attachment may be removed from Attachments and
    # ArchiveAttachments in the same run; prevent warnings from the
    # backing store by only removing it from there once.
    already_removed = set()
    for attachment in old_unclaimed_attachments:
        delete_message_attachment(attachment.path_id)
        already_removed.add(attachment.path_id)
        attachment.delete()
    for archived_attachment in old_unclaimed_archived_attachments:
        if archived_attachment.path_id not in already_removed:
            delete_message_attachment(archived_attachment.path_id)
        archived_attachment.delete()


def check_attachment_reference_change(
    message: Union[Message, ScheduledMessage], rendering_result: MessageRenderingResult
) -> bool:
    # For a unsaved message edit (message.* has been updated, but not
    # saved to the database), adjusts Attachment data to correspond to
    # the new content.
    prev_attachments = {a.path_id for a in message.attachment_set.all()}
    new_attachments = set(rendering_result.potential_attachment_path_ids)

    if new_attachments == prev_attachments:
        return bool(prev_attachments)

    to_remove = list(prev_attachments - new_attachments)
    if len(to_remove) > 0:
        attachments_to_update = Attachment.objects.filter(path_id__in=to_remove).select_for_update()
        message.attachment_set.remove(*attachments_to_update)

    to_add = list(new_attachments - prev_attachments)
    if len(to_add) > 0:
        do_claim_attachments(message, to_add)

    return message.attachment_set.exists()

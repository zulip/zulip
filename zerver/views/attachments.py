from django.db import transaction
from django.http import HttpRequest, HttpResponse

from zerver.actions.uploads import notify_attachment_update
from zerver.lib.attachments import access_attachment_by_id, remove_attachment, user_attachments
from zerver.lib.message import event_recipient_ids_for_action_on_messages
from zerver.lib.response import json_success
from zerver.models import UserProfile


def list_by_user(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(
        request,
        data={
            "attachments": user_attachments(user_profile),
            "upload_space_used": user_profile.realm.currently_used_upload_space_bytes(),
        },
    )


@transaction.atomic(durable=True)
def remove(request: HttpRequest, user_profile: UserProfile, attachment_id: int) -> HttpResponse:
    attachment = access_attachment_by_id(user_profile, attachment_id, needs_owner=True)

    # Get all messages that contain this attachment
    messages = list(attachment.messages.all())

    # Store message IDs before deletion for client-side re-rendering
    message_ids = [message.id for message in messages]

    # Calculate all user IDs who should be notified
    user_ids_to_notify: set[int] = set()

    if messages:
        # Group messages by recipient so each call to
        # event_recipient_ids_for_action_on_messages has messages
        # from a single conversation.
        messages_by_recipient: dict[int, tuple[bool, list[int]]] = {}
        for message in messages:
            key = message.recipient_id
            if key not in messages_by_recipient:
                messages_by_recipient[key] = (message.is_channel_message, [])
            messages_by_recipient[key][1].append(message.id)

        for is_channel_message, msg_ids in messages_by_recipient.values():
            user_ids_to_notify.update(
                event_recipient_ids_for_action_on_messages(
                    msg_ids,
                    is_channel_message=is_channel_message,
                )
            )

    # Always include the owner
    user_ids_to_notify.add(user_profile.id)

    # Save path_id before deletion for client-side inline preview removal
    path_id = attachment.path_id

    # Remove the attachment
    remove_attachment(user_profile, attachment)

    # Notify all recipients with message IDs and path_id so clients can
    # remove inline previews for the deleted attachment in real-time.
    notify_attachment_update(
        user_profile,
        "remove",
        {"id": attachment_id, "message_ids": message_ids, "path_id": path_id},
        user_ids=list(user_ids_to_notify),
    )
    return json_success(request)

from django.db import transaction
from django.http import HttpRequest, HttpResponse

from zerver.actions.uploads import notify_attachment_update
from zerver.lib.attachments import access_attachment_by_id, remove_attachment, user_attachments
from zerver.lib.message import event_recipient_ids_for_action_on_messages
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id
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
        # Group messages by type (channel vs DM) to use event_recipient_ids_for_action_on_messages
        # efficiently. We need to separate channel and DM messages since they're handled differently.
        channel_messages = []
        dm_messages = []

        for message in messages:
            if message.is_channel_message:
                channel_messages.append(message)
            else:
                dm_messages.append(message)

        # Get recipients for DM messages
        if dm_messages:
            dm_message_ids = [m.id for m in dm_messages]
            user_ids_to_notify.update(
                event_recipient_ids_for_action_on_messages(
                    dm_message_ids,
                    is_channel_message=False,
                )
            )

        # Get recipients for channel messages, grouped by channel
        if channel_messages:
            # Group by channel to optimize the query
            messages_by_channel: dict[int, list[int]] = {}
            for message in channel_messages:
                stream_id = message.recipient.type_id
                if stream_id not in messages_by_channel:
                    messages_by_channel[stream_id] = []
                messages_by_channel[stream_id].append(message.id)

            # Get recipients for each channel
            for stream_id, msg_ids in messages_by_channel.items():
                stream, _sub = access_stream_by_id(
                    user_profile, stream_id, require_content_access=False
                )
                user_ids_to_notify.update(
                    event_recipient_ids_for_action_on_messages(
                        msg_ids,
                        is_channel_message=True,
                        channel=stream,
                    )
                )

    # Always include the owner
    user_ids_to_notify.add(user_profile.id)

    # Remove the attachment
    remove_attachment(user_profile, attachment)

    # Notify all recipients with message IDs so they can refresh those messages
    notify_attachment_update(
        user_profile,
        "remove",
        {"id": attachment_id, "message_ids": message_ids},
        user_ids=list(user_ids_to_notify),
    )
    return json_success(request)

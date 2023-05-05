import datetime
from typing import List, Optional, Sequence, Tuple, Union

import orjson
from django.db import transaction
from django.utils.translation import gettext as _

from zerver.actions.message_send import check_message, do_send_messages
from zerver.actions.uploads import check_attachment_reference_change, do_claim_attachments
from zerver.lib.addressee import Addressee
from zerver.lib.exceptions import JsonableError, RealmDeactivatedError, UserDeactivatedError
from zerver.lib.message import SendMessageRequest, render_markdown
from zerver.lib.scheduled_messages import access_scheduled_message
from zerver.models import (
    Client,
    Realm,
    ScheduledMessage,
    Subscription,
    UserProfile,
)
from zerver.tornado.django_api import send_event


def extract_stream_id(req_to: str) -> List[int]:
    # Recipient should only be a single stream ID.
    try:
        stream_id = int(req_to)
    except ValueError:
        raise JsonableError(_("Invalid data type for stream ID"))
    return [stream_id]


def extract_direct_message_recipient_ids(req_to: str) -> List[int]:
    try:
        user_ids = orjson.loads(req_to)
    except orjson.JSONDecodeError:
        user_ids = req_to

    if not isinstance(user_ids, list):
        raise JsonableError(_("Invalid data type for recipients"))

    for user_id in user_ids:
        if not isinstance(user_id, int):
            raise JsonableError(_("Recipient list may only contain user IDs"))

    return list(set(user_ids))


def check_schedule_message(
    sender: UserProfile,
    client: Client,
    recipient_type_name: str,
    message_to: Union[Sequence[str], Sequence[int]],
    topic_name: Optional[str],
    message_content: str,
    scheduled_message_id: Optional[int],
    deliver_at: datetime.datetime,
    realm: Optional[Realm] = None,
    forwarder_user_profile: Optional[UserProfile] = None,
) -> int:
    addressee = Addressee.legacy_build(sender, recipient_type_name, message_to, topic_name)
    send_request = check_message(
        sender,
        client,
        addressee,
        message_content,
        realm=realm,
        forwarder_user_profile=forwarder_user_profile,
    )
    send_request.deliver_at = deliver_at

    if scheduled_message_id is not None:
        return edit_scheduled_message(scheduled_message_id, send_request, sender)

    return do_schedule_messages([send_request], sender)[0]


def do_schedule_messages(
    send_message_requests: Sequence[SendMessageRequest], sender: UserProfile
) -> List[int]:
    scheduled_messages: List[Tuple[ScheduledMessage, SendMessageRequest]] = []

    for send_request in send_message_requests:
        scheduled_message = ScheduledMessage()
        scheduled_message.sender = send_request.message.sender
        scheduled_message.recipient = send_request.message.recipient
        topic_name = send_request.message.topic_name()
        scheduled_message.set_topic_name(topic_name=topic_name)
        rendering_result = render_markdown(
            send_request.message, send_request.message.content, send_request.realm
        )
        scheduled_message.content = send_request.message.content
        scheduled_message.rendered_content = rendering_result.rendered_content
        scheduled_message.sending_client = send_request.message.sending_client
        scheduled_message.stream = send_request.stream
        scheduled_message.realm = send_request.realm
        assert send_request.deliver_at is not None
        scheduled_message.scheduled_timestamp = send_request.deliver_at
        scheduled_message.delivery_type = ScheduledMessage.SEND_LATER

        scheduled_messages.append((scheduled_message, send_request))

    with transaction.atomic():
        ScheduledMessage.objects.bulk_create(
            [scheduled_message for scheduled_message, ignored in scheduled_messages]
        )
        for scheduled_message, send_request in scheduled_messages:
            if do_claim_attachments(
                scheduled_message, send_request.rendering_result.potential_attachment_path_ids
            ):
                scheduled_message.has_attachment = True
                scheduled_message.save(update_fields=["has_attachment"])

    event = {
        "type": "scheduled_messages",
        "op": "add",
        "scheduled_messages": [
            scheduled_message.to_dict() for scheduled_message, ignored in scheduled_messages
        ],
    }
    send_event(sender.realm, event, [sender.id])
    return [scheduled_message.id for scheduled_message, ignored in scheduled_messages]


def edit_scheduled_message(
    scheduled_message_id: int, send_request: SendMessageRequest, sender: UserProfile
) -> int:
    with transaction.atomic():
        scheduled_message_object = access_scheduled_message(sender, scheduled_message_id)

        # Handles the race between us initiating this transaction and user sending us the edit request.
        if scheduled_message_object.delivered is True:
            raise JsonableError(_("Scheduled message was already sent"))

        # Only override fields that user can change.
        scheduled_message_object.recipient = send_request.message.recipient
        topic_name = send_request.message.topic_name()
        scheduled_message_object.set_topic_name(topic_name=topic_name)
        rendering_result = render_markdown(
            send_request.message, send_request.message.content, send_request.realm
        )
        scheduled_message_object.content = send_request.message.content
        scheduled_message_object.rendered_content = rendering_result.rendered_content
        scheduled_message_object.sending_client = send_request.message.sending_client
        scheduled_message_object.stream = send_request.stream
        assert send_request.deliver_at is not None
        scheduled_message_object.scheduled_timestamp = send_request.deliver_at

        scheduled_message_object.has_attachment = check_attachment_reference_change(
            scheduled_message_object, rendering_result
        )

        scheduled_message_object.save()

    event = {
        "type": "scheduled_messages",
        "op": "update",
        "scheduled_message": scheduled_message_object.to_dict(),
    }
    send_event(sender.realm, event, [sender.id])
    return scheduled_message_id


def notify_remove_scheduled_message(user_profile: UserProfile, scheduled_message_id: int) -> None:
    event = {
        "type": "scheduled_messages",
        "op": "remove",
        "scheduled_message_id": scheduled_message_id,
    }
    send_event(user_profile.realm, event, [user_profile.id])


def delete_scheduled_message(user_profile: UserProfile, scheduled_message_id: int) -> None:
    scheduled_message_object = access_scheduled_message(user_profile, scheduled_message_id)
    scheduled_message_id = scheduled_message_object.id
    scheduled_message_object.delete()

    notify_remove_scheduled_message(user_profile, scheduled_message_id)


def send_scheduled_message(scheduled_message: ScheduledMessage) -> None:
    assert not scheduled_message.delivered
    assert not scheduled_message.failed

    # It's currently not possible to use the reminder feature.
    assert scheduled_message.delivery_type == ScheduledMessage.SEND_LATER

    # Repeat the checks from validate_account_and_subdomain, in case
    # the state changed since the message as scheduled.
    if scheduled_message.realm.deactivated:
        raise RealmDeactivatedError

    if not scheduled_message.sender.is_active:
        raise UserDeactivatedError

    # Recheck that we have permission to send this message, in case
    # permissions have changed since the message was scheduled.
    if scheduled_message.stream is not None:
        addressee = Addressee.for_stream(scheduled_message.stream, scheduled_message.topic_name())
    else:
        subscriber_ids = list(
            Subscription.objects.filter(recipient=scheduled_message.recipient).values_list(
                "user_profile_id", flat=True
            )
        )
        addressee = Addressee.for_user_ids(subscriber_ids, scheduled_message.realm)

    # Calling check_message again is important because permissions may
    # have changed since the message was originally scheduled. This
    # means that Markdown syntax referencing mutable organization data
    # (for example, mentioning a user by name) will work (or not) as
    # if the message was sent at the delviery time, not the sending
    # time.
    send_request = check_message(
        scheduled_message.sender,
        scheduled_message.sending_client,
        addressee,
        scheduled_message.content,
        scheduled_message.realm,
    )

    # TODO: Store the resulting message ID on the scheduled_message object.
    do_send_messages([send_request])
    scheduled_message.delivered = True
    scheduled_message.save(update_fields=["delivered"])
    notify_remove_scheduled_message(scheduled_message.sender, scheduled_message.id)

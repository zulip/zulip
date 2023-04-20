import datetime
from typing import List, Optional, Sequence, Union

from django.db import transaction
from django.utils.translation import gettext as _

from zerver.actions.message_send import check_message
from zerver.lib.addressee import Addressee
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import SendMessageRequest, render_markdown
from zerver.lib.scheduled_messages import access_scheduled_message
from zerver.models import Client, Realm, ScheduledMessage, UserProfile
from zerver.tornado.django_api import send_event


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

    return do_schedule_messages([send_request])[0]


def do_schedule_messages(send_message_requests: Sequence[SendMessageRequest]) -> List[int]:
    scheduled_messages: List[ScheduledMessage] = []

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

        scheduled_messages.append(scheduled_message)

    ScheduledMessage.objects.bulk_create(scheduled_messages)
    return [scheduled_message.id for scheduled_message in scheduled_messages]


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
        scheduled_message_object.save()
    return scheduled_message_id


def delete_scheduled_message(user_profile: UserProfile, scheduled_message_id: int) -> None:
    scheduled_message_object = access_scheduled_message(user_profile, scheduled_message_id)
    scheduled_message_id = scheduled_message_object.id
    scheduled_message_object.delete()

    event = {
        "type": "scheduled_message",
        "op": "remove",
        "scheduled_message_id": scheduled_message_id,
    }
    send_event(user_profile.realm, event, [user_profile.id])

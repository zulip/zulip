import datetime
import logging
from typing import List, Optional, Sequence, Tuple

import orjson
from django.conf import settings
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language

from zerver.actions.message_send import (
    check_message,
    do_send_messages,
    internal_send_private_message,
)
from zerver.actions.uploads import check_attachment_reference_change, do_claim_attachments
from zerver.lib.addressee import Addressee
from zerver.lib.exceptions import JsonableError, RealmDeactivatedError, UserDeactivatedError
from zerver.lib.message import SendMessageRequest, render_markdown, truncate_topic
from zerver.lib.scheduled_messages import access_scheduled_message
from zerver.lib.string_validation import check_stream_topic
from zerver.models import (
    Client,
    Realm,
    ScheduledMessage,
    Subscription,
    UserProfile,
    get_recipient_ids,
    get_system_bot,
)
from zerver.tornado.django_api import send_event

SCHEDULED_MESSAGE_LATE_CUTOFF_MINUTES = 10


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
    message_to: List[int],
    topic_name: Optional[str],
    message_content: str,
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


def notify_update_scheduled_message(
    user_profile: UserProfile, scheduled_message: ScheduledMessage
) -> None:
    event = {
        "type": "scheduled_messages",
        "op": "update",
        "scheduled_message": scheduled_message.to_dict(),
    }
    send_event(user_profile.realm, event, [user_profile.id])


def edit_scheduled_message(
    sender: UserProfile,
    client: Client,
    scheduled_message_id: int,
    recipient_type_name: Optional[str],
    message_to: Optional[str],
    topic_name: Optional[str],
    message_content: Optional[str],
    deliver_at: Optional[datetime.datetime],
    realm: Realm,
) -> None:
    with transaction.atomic():
        scheduled_message_object = access_scheduled_message(sender, scheduled_message_id)

        # Handles the race between us initiating this transaction and user sending us the edit request.
        if scheduled_message_object.delivered is True:
            raise JsonableError(_("Scheduled message was already sent"))

        # If the server failed to send the scheduled message, a new scheduled
        # delivery timestamp (`deliver_at`) is required.
        if scheduled_message_object.failed and deliver_at is None:
            raise JsonableError(_("Scheduled delivery time must be in the future."))

        # Get existing scheduled message's recipient IDs and recipient_type_name.
        existing_recipient, existing_recipient_type_name = get_recipient_ids(
            scheduled_message_object.recipient, sender.id
        )

        # If any recipient information or message content has been updated,
        # we check the message again.
        if recipient_type_name is not None or message_to is not None or message_content is not None:
            # Update message type if changed.
            if recipient_type_name is not None:
                updated_recipient_type_name = recipient_type_name
            else:
                updated_recipient_type_name = existing_recipient_type_name

            # Update message recipient if changed.
            if message_to is not None:
                if updated_recipient_type_name == "stream":
                    updated_recipient = extract_stream_id(message_to)
                else:
                    updated_recipient = extract_direct_message_recipient_ids(message_to)
            else:
                updated_recipient = existing_recipient

            # Update topic name if changed.
            if topic_name is not None:
                updated_topic = topic_name
            else:
                # This will be ignored in Addressee.legacy_build if type
                # is being changed from stream to direct.
                updated_topic = scheduled_message_object.topic_name()

            # Update message content if changed.
            if message_content is not None:
                updated_content = message_content
            else:
                updated_content = scheduled_message_object.content

            # Check message again.
            addressee = Addressee.legacy_build(
                sender, updated_recipient_type_name, updated_recipient, updated_topic
            )
            send_request = check_message(
                sender,
                client,
                addressee,
                updated_content,
                realm=realm,
                forwarder_user_profile=sender,
            )

        if recipient_type_name is not None or message_to is not None:
            # User has updated the scheduled message's recipient.
            scheduled_message_object.recipient = send_request.message.recipient
            scheduled_message_object.stream = send_request.stream
            # Update the topic based on the new recipient information.
            new_topic_name = send_request.message.topic_name()
            scheduled_message_object.set_topic_name(topic_name=new_topic_name)
        elif topic_name is not None and existing_recipient_type_name == "stream":
            # User has updated the scheduled message's topic, but not
            # the existing recipient information. We ignore topics sent
            # for scheduled direct messages.
            check_stream_topic(topic_name)
            new_topic_name = truncate_topic(topic_name)
            scheduled_message_object.set_topic_name(topic_name=new_topic_name)

        if message_content is not None:
            # User has updated the scheduled messages's content.
            rendering_result = render_markdown(
                send_request.message, send_request.message.content, send_request.realm
            )
            scheduled_message_object.content = send_request.message.content
            scheduled_message_object.rendered_content = rendering_result.rendered_content
            scheduled_message_object.has_attachment = check_attachment_reference_change(
                scheduled_message_object, rendering_result
            )

        if deliver_at is not None:
            # User has updated the scheduled message's send timestamp.
            scheduled_message_object.scheduled_timestamp = deliver_at

        # Update for most recent Client information.
        scheduled_message_object.sending_client = client

        # If the user is editing a scheduled message that the server tried
        # and failed to send, we need to update the `failed` boolean field
        # as well as the associated `failure_message` field.
        if scheduled_message_object.failed:
            scheduled_message_object.failed = False
            scheduled_message_object.failure_message = None

        scheduled_message_object.save()

    notify_update_scheduled_message(sender, scheduled_message_object)


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

    # Limit how late we're willing to send a scheduled message.
    latest_send_time = scheduled_message.scheduled_timestamp + datetime.timedelta(
        minutes=SCHEDULED_MESSAGE_LATE_CUTOFF_MINUTES
    )
    if timezone_now() > latest_send_time:
        raise JsonableError(_("Message could not be sent at the scheduled time."))

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

    scheduled_message_to_self = scheduled_message.recipient == scheduled_message.sender.recipient
    message_id = do_send_messages(
        [send_request], scheduled_message_to_self=scheduled_message_to_self
    )[0]
    scheduled_message.delivered_message_id = message_id
    scheduled_message.delivered = True
    scheduled_message.save(update_fields=["delivered", "delivered_message_id"])
    notify_remove_scheduled_message(scheduled_message.sender, scheduled_message.id)


def send_failed_scheduled_message_notification(
    user_profile: UserProfile, scheduled_message_id: int
) -> None:
    scheduled_message = access_scheduled_message(user_profile, scheduled_message_id)
    delivery_datetime_string = str(scheduled_message.scheduled_timestamp)

    with override_language(user_profile.default_language):
        error_string = scheduled_message.failure_message
        delivery_time_markdown = f"<time:{delivery_datetime_string}> "

        content = "".join(
            [
                _(
                    "The message you scheduled for {delivery_datetime} was not sent because of the following error:"
                ),
                "\n\n",
                "> {error_message}",
                "\n\n",
                _("[View scheduled messages](#scheduled)"),
                "\n\n",
            ]
        )

    content = content.format(
        delivery_datetime=delivery_time_markdown,
        error_message=error_string,
    )

    internal_send_private_message(
        get_system_bot(settings.NOTIFICATION_BOT, user_profile.realm_id),
        user_profile,
        content,
    )


@transaction.atomic
def try_deliver_one_scheduled_message(logger: logging.Logger) -> bool:
    # Returns whether there was a scheduled message to attempt
    # delivery on, regardless of whether delivery succeeded.
    scheduled_message = (
        ScheduledMessage.objects.filter(
            scheduled_timestamp__lte=timezone_now(),
            delivered=False,
            failed=False,
        )
        .select_for_update()
        .first()
    )

    if scheduled_message is None:
        return False

    logger.info(
        "Sending scheduled message %s with date %s (sender: %s)",
        scheduled_message.id,
        scheduled_message.scheduled_timestamp,
        scheduled_message.sender_id,
    )

    with override_language(scheduled_message.sender.default_language):
        try:
            send_scheduled_message(scheduled_message)
        except Exception as e:
            scheduled_message.refresh_from_db()
            was_delivered = scheduled_message.delivered
            scheduled_message.failed = True

            if isinstance(e, JsonableError):
                scheduled_message.failure_message = e.msg
                logger.info("Failed with message: %s", e.msg)
            else:
                # An unexpected failure; store and send user a generic
                # internal server error in notification message.
                scheduled_message.failure_message = _("Internal server error")
                logger.exception(
                    "Unexpected error sending scheduled message %s (sent: %s)",
                    scheduled_message.id,
                    was_delivered,
                    stack_info=True,
                )

            scheduled_message.save(update_fields=["failed", "failure_message"])

            if (
                not was_delivered
                # Do not send notification if either the realm or
                # the sending user account has been deactivated.
                and not isinstance(e, RealmDeactivatedError)
                and not isinstance(e, UserDeactivatedError)
            ):
                notify_update_scheduled_message(scheduled_message.sender, scheduled_message)
                send_failed_scheduled_message_notification(
                    scheduled_message.sender, scheduled_message.id
                )

    return True

from typing import Literal

from django.conf import settings
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.stream_subscription import get_active_subscriptions_for_stream_id
from zerver.models import Realm, Stream, UserProfile
from zerver.models.users import get_user_by_id_in_realm_including_cross_realm
from zerver.tornado.django_api import send_event_rollback_unsafe


def do_send_typing_notification(
    realm: Realm, sender: UserProfile, recipient_user_profiles: list[UserProfile], operator: str
) -> None:
    sender_dict = {"user_id": sender.id, "email": sender.email}

    # Include a list of recipients in the event body to help identify where the typing is happening
    recipient_dicts = [
        {"user_id": profile.id, "email": profile.email} for profile in recipient_user_profiles
    ]
    event = dict(
        type="typing",
        message_type="direct",
        op=operator,
        sender=sender_dict,
        recipients=recipient_dicts,
    )

    # Only deliver the notification to active user recipients
    user_ids_to_notify = [
        user.id
        for user in recipient_user_profiles
        if user.is_active and user.receives_typing_notifications
    ]

    send_event_rollback_unsafe(realm, event, user_ids_to_notify)


# check_send_typing_notification:
# Checks the typing notification and sends it
def check_send_typing_notification(sender: UserProfile, user_ids: list[int], operator: str) -> None:
    realm = sender.realm

    if sender.id not in user_ids:
        user_ids.append(sender.id)

    # If any of the user_ids being sent in are invalid, we will
    # just reject the whole request, since a partial list of user_ids
    # can create confusion related to direct message groups. Plus it's
    # a good sign that a client is confused (or possibly even malicious)
    # if we get bad user_ids.
    user_profiles = []
    for user_id in user_ids:
        try:
            # We include cross-bot realms as possible recipients,
            # so that clients can know which direct message group
            # conversation is relevant here.
            user_profile = get_user_by_id_in_realm_including_cross_realm(user_id, sender.realm)
        except UserProfile.DoesNotExist:
            raise JsonableError(_("Invalid user ID {user_id}").format(user_id=user_id))
        user_profiles.append(user_profile)

    do_send_typing_notification(
        realm=realm,
        sender=sender,
        recipient_user_profiles=user_profiles,
        operator=operator,
    )


def do_send_stream_typing_notification(
    sender: UserProfile, operator: str, stream: Stream, topic_name: str
) -> None:
    sender_dict = {"user_id": sender.id, "email": sender.email}

    event = dict(
        type="typing",
        message_type="stream",
        op=operator,
        sender=sender_dict,
        stream_id=stream.id,
        topic=topic_name,
    )

    subscriptions_query = get_active_subscriptions_for_stream_id(
        stream.id, include_deactivated_users=False
    )

    total_subscriptions = subscriptions_query.count()
    if total_subscriptions > settings.MAX_STREAM_SIZE_FOR_TYPING_NOTIFICATIONS:
        # TODO: Stream typing notifications are disabled in streams
        # with too many subscribers for performance reasons.
        return

    user_ids_to_notify = set(
        subscriptions_query.exclude(user_profile__long_term_idle=True)
        .exclude(user_profile__receives_typing_notifications=False)
        .values_list("user_profile_id", flat=True)
    )

    send_event_rollback_unsafe(sender.realm, event, user_ids_to_notify)


def do_send_stream_message_edit_typing_notification(
    sender: UserProfile,
    channel_id: int,
    message_id: int,
    operator: Literal["start", "stop"],
    topic_name: str,
) -> None:
    event = dict(
        type="typing_edit_message",
        op=operator,
        sender_id=sender.id,
        message_id=message_id,
        recipient=dict(
            type="channel",
            channel_id=channel_id,
            topic=topic_name,
        ),
    )

    subscriptions_query = get_active_subscriptions_for_stream_id(
        channel_id, include_deactivated_users=False
    )

    total_subscriptions = subscriptions_query.count()
    if total_subscriptions > settings.MAX_STREAM_SIZE_FOR_TYPING_NOTIFICATIONS:
        # TODO: Stream typing notifications are disabled in streams
        # with too many subscribers for performance reasons.
        return

    # We don't notify long_term_idle subscribers.
    user_ids_to_notify = set(
        subscriptions_query.exclude(user_profile__long_term_idle=True)
        .exclude(user_profile__receives_typing_notifications=False)
        .values_list("user_profile_id", flat=True)
    )

    send_event_rollback_unsafe(sender.realm, event, user_ids_to_notify)


def do_send_direct_message_edit_typing_notification(
    sender: UserProfile,
    user_ids: list[int],
    message_id: int,
    operator: Literal["start", "stop"],
) -> None:
    recipient_user_profiles = []
    for user_id in user_ids:
        user_profile = get_user_by_id_in_realm_including_cross_realm(user_id, sender.realm)
        recipient_user_profiles.append(user_profile)

    # Only deliver the notification to active user recipients
    user_ids_to_notify = [
        user.id
        for user in recipient_user_profiles
        if user.is_active and user.receives_typing_notifications
    ]

    event = dict(
        type="typing_edit_message",
        op=operator,
        sender_id=sender.id,
        message_id=message_id,
        recipient=dict(
            type="direct",
            user_ids=user_ids_to_notify,
        ),
    )

    send_event_rollback_unsafe(sender.realm, event, user_ids_to_notify)

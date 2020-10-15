from typing import Any, Dict, List, Optional, Set, Tuple

from django.db.models.query import QuerySet

from zerver.models import Recipient, Stream, Subscription, UserProfile


def get_active_subscriptions_for_stream_id(stream_id: int) -> QuerySet:
    # TODO: Change return type to QuerySet[Subscription]
    return Subscription.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id=stream_id,
        active=True,
    )

def get_active_subscriptions_for_stream_ids(stream_ids: Set[int]) -> QuerySet:
    # TODO: Change return type to QuerySet[Subscription]
    return Subscription.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=stream_ids,
        active=True,
    )

def get_subscribed_stream_ids_for_user(user_profile: UserProfile) -> QuerySet:
    return Subscription.objects.filter(
        user_profile_id=user_profile,
        recipient__type=Recipient.STREAM,
        active=True,
    ).values_list('recipient__type_id', flat=True)

def get_stream_subscriptions_for_user(user_profile: UserProfile) -> QuerySet:
    # TODO: Change return type to QuerySet[Subscription]
    return Subscription.objects.filter(
        user_profile=user_profile,
        recipient__type=Recipient.STREAM,
    )

def get_stream_subscriptions_for_users(user_profiles: List[UserProfile]) -> QuerySet:
    # TODO: Change return type to QuerySet[Subscription]
    return Subscription.objects.filter(
        user_profile__in=user_profiles,
        recipient__type=Recipient.STREAM,
    )

def get_bulk_stream_subscriber_info(
        user_profiles: List[UserProfile],
        stream_dict: Dict[int, Stream]) -> Dict[int, List[Tuple[Subscription, Stream]]]:

    stream_ids = stream_dict.keys()

    result: Dict[int, List[Tuple[Subscription, Stream]]] = {
        user_profile.id: []
        for user_profile in user_profiles
    }

    subs = Subscription.objects.filter(
        user_profile__in=user_profiles,
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=stream_ids,
        active=True,
    ).select_related('user_profile', 'recipient')

    for sub in subs:
        user_profile_id = sub.user_profile_id
        stream_id = sub.recipient.type_id
        stream = stream_dict[stream_id]
        result[user_profile_id].append((sub, stream))

    return result

def num_subscribers_for_stream_id(stream_id: int) -> int:
    return get_active_subscriptions_for_stream_id(stream_id).filter(
        user_profile__is_active=True,
    ).count()


def handle_stream_notifications_compatibility(user_profile: Optional[UserProfile],
                                              stream_dict: Dict[str, Any],
                                              notification_settings_null: bool) -> None:
    # Old versions of the mobile apps don't support `None` as a
    # value for the stream-level notifications properties, so we
    # have to handle the normally frontend-side defaults for these
    # settings here for those older clients.
    #
    # Note that this situation results in these older mobile apps
    # having a subtle bug where changes to the user-level stream
    # notification defaults will not properly propagate to the
    # mobile app "stream notification settings" UI until the app
    # re-registers.  This is an acceptable level of
    # backwards-compatibility problem in our view.
    assert not notification_settings_null

    for notification_type in ["desktop_notifications", "audible_notifications",
                              "push_notifications", "email_notifications"]:
        # Values of true/false are supported by older clients.
        if stream_dict[notification_type] is not None:
            continue
        target_attr = "enable_stream_" + notification_type
        stream_dict[notification_type] = False if user_profile is None else getattr(user_profile, target_attr)

from typing import Dict, List, Tuple
from mypy_extensions import TypedDict

from django.db.models.query import QuerySet
from zerver.models import (
    Recipient,
    Stream,
    Subscription,
    UserProfile,
)

def get_active_subscriptions_for_stream_id(stream_id: int) -> QuerySet:
    # TODO: Change return type to QuerySet[Subscription]
    return Subscription.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id=stream_id,
        active=True,
    )

def get_active_subscriptions_for_stream_ids(stream_ids: List[int]) -> QuerySet:
    # TODO: Change return type to QuerySet[Subscription]
    return Subscription.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=stream_ids,
        active=True
    )

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

SubInfo = TypedDict('SubInfo', {
    'sub': Subscription,
    'stream': Stream,
})

def get_bulk_stream_subscriber_info(
        user_profiles: List[UserProfile],
        stream_dict: Dict[int, Stream]) -> Dict[int, List[Tuple[Subscription, Stream]]]:

    stream_ids = stream_dict.keys()

    result = {
        user_profile.id: []
        for user_profile in user_profiles
    }  # type: Dict[int, List[Tuple[Subscription, Stream]]]

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

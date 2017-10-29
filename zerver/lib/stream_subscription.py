from typing import List

from django.db.models.query import QuerySet
from zerver.models import (
    Recipient,
    Subscription,
    UserProfile,
)

def get_active_subscriptions_for_stream_id(stream_id):
    # type: (int) -> QuerySet
    return Subscription.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id=stream_id,
        active=True,
    )

def get_active_subscriptions_for_stream_ids(stream_ids):
    # type: (List[int]) -> QuerySet
    return Subscription.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=stream_ids,
        active=True
    )

def get_stream_subscriptions_for_user(user_profile):
    # type: (UserProfile) -> QuerySet
    return Subscription.objects.filter(
        user_profile=user_profile,
        recipient__type=Recipient.STREAM,
    )

def get_stream_subscriptions_for_users(user_profiles):
    # type: (List[UserProfile]) -> QuerySet
    return Subscription.objects.filter(
        user_profile__in=user_profiles,
        recipient__type=Recipient.STREAM,
    )

def num_subscribers_for_stream_id(stream_id):
    # type: (int) -> int
    return get_active_subscriptions_for_stream_id(stream_id).filter(
        user_profile__is_active=True,
    ).count()

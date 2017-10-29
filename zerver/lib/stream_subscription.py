from django.db.models.query import QuerySet
from zerver.models import (
    Recipient,
    Subscription,
)

def get_active_subscriptions_for_stream_id(stream_id):
    # type: (int) -> QuerySet
    return Subscription.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id=stream_id,
        active=True,
    )

def num_subscribers_for_stream_id(stream_id):
    # type: (int) -> int
    return get_active_subscriptions_for_stream_id(stream_id).filter(
        user_profile__is_active=True,
    ).count()

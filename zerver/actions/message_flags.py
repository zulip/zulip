import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import List, Optional, Set

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import (
    bulk_access_messages,
    format_unread_message_details,
    get_raw_unread_data,
)
from zerver.lib.queue import queue_json_publish
from zerver.lib.stream_subscription import get_subscribed_stream_recipient_ids_for_user
from zerver.lib.topic import filter_by_topic_name_via_message
from zerver.lib.user_message import DEFAULT_HISTORICAL_FLAGS, create_historical_user_messages
from zerver.models import Message, Recipient, UserMessage, UserProfile
from zerver.tornado.django_api import send_event


@dataclass
class ReadMessagesEvent:
    messages: List[int]
    all: bool
    type: str = field(default="update_message_flags", init=False)
    op: str = field(default="add", init=False)
    operation: str = field(default="add", init=False)
    flag: str = field(default="read", init=False)


def do_mark_all_as_read(
    user_profile: UserProfile, *, timeout: Optional[float] = None
) -> Optional[int]:
    start_time = time.monotonic()

    # First, we clear mobile push notifications.  This is safer in the
    # event that the below logic times out and we're killed.
    all_push_message_ids = (
        UserMessage.objects.filter(
            user_profile=user_profile,
        )
        .extra(
            where=[UserMessage.where_active_push_notification()],
        )
        .values_list("message_id", flat=True)[0:10000]
    )
    do_clear_mobile_push_notifications_for_ids([user_profile.id], all_push_message_ids)

    batch_size = 2000
    count = 0
    while True:
        if timeout is not None and time.monotonic() >= start_time + timeout:
            return None

        with transaction.atomic(savepoint=False):
            query = (
                UserMessage.select_for_update_query()
                .filter(user_profile=user_profile)
                .extra(where=[UserMessage.where_unread()])[:batch_size]
            )
            # This updated_count is the same as the number of UserMessage
            # rows selected, because due to the FOR UPDATE lock, we're guaranteed
            # that all the selected rows will indeed be updated.
            # UPDATE queries don't support LIMIT, so we have to use a subquery
            # to do batching.
            updated_count = UserMessage.objects.filter(id__in=query).update(
                flags=F("flags").bitor(UserMessage.flags.read),
            )

            event_time = timezone_now()
            do_increment_logging_stat(
                user_profile,
                COUNT_STATS["messages_read::hour"],
                None,
                event_time,
                increment=updated_count,
            )
            do_increment_logging_stat(
                user_profile,
                COUNT_STATS["messages_read_interactions::hour"],
                None,
                event_time,
                increment=min(1, updated_count),
            )

            count += updated_count
            if updated_count < batch_size:
                break

    event = asdict(
        ReadMessagesEvent(
            messages=[],  # we don't send messages, since the client reloads anyway
            all=True,
        )
    )
    send_event(user_profile.realm, event, [user_profile.id])

    return count


def do_mark_stream_messages_as_read(
    user_profile: UserProfile, stream_recipient_id: int, topic_name: Optional[str] = None
) -> int:
    with transaction.atomic(savepoint=False):
        query = (
            UserMessage.select_for_update_query()
            .filter(
                user_profile=user_profile,
                message__recipient_id=stream_recipient_id,
            )
            .extra(
                where=[UserMessage.where_unread()],
            )
        )

        if topic_name:
            query = filter_by_topic_name_via_message(
                query=query,
                topic_name=topic_name,
            )

        message_ids = list(query.values_list("message_id", flat=True))

        if len(message_ids) == 0:
            return 0

        count = query.update(
            flags=F("flags").bitor(UserMessage.flags.read),
        )

    event = asdict(
        ReadMessagesEvent(
            messages=message_ids,
            all=False,
        )
    )
    event_time = timezone_now()

    send_event(user_profile.realm, event, [user_profile.id])
    do_clear_mobile_push_notifications_for_ids([user_profile.id], message_ids)

    do_increment_logging_stat(
        user_profile, COUNT_STATS["messages_read::hour"], None, event_time, increment=count
    )
    do_increment_logging_stat(
        user_profile,
        COUNT_STATS["messages_read_interactions::hour"],
        None,
        event_time,
        increment=min(1, count),
    )
    return count


def do_mark_muted_user_messages_as_read(
    user_profile: UserProfile,
    muted_user: UserProfile,
) -> int:
    with transaction.atomic(savepoint=False):
        query = (
            UserMessage.select_for_update_query()
            .filter(user_profile=user_profile, message__sender=muted_user)
            .extra(where=[UserMessage.where_unread()])
        )
        message_ids = list(query.values_list("message_id", flat=True))

        if len(message_ids) == 0:
            return 0

        count = query.update(
            flags=F("flags").bitor(UserMessage.flags.read),
        )

    event = asdict(
        ReadMessagesEvent(
            messages=message_ids,
            all=False,
        )
    )
    event_time = timezone_now()

    send_event(user_profile.realm, event, [user_profile.id])
    do_clear_mobile_push_notifications_for_ids([user_profile.id], message_ids)

    do_increment_logging_stat(
        user_profile, COUNT_STATS["messages_read::hour"], None, event_time, increment=count
    )
    do_increment_logging_stat(
        user_profile,
        COUNT_STATS["messages_read_interactions::hour"],
        None,
        event_time,
        increment=min(1, count),
    )
    return count


def do_update_mobile_push_notification(
    message: Message,
    prior_mention_user_ids: Set[int],
    mentions_user_ids: Set[int],
    stream_push_user_ids: Set[int],
) -> None:
    # Called during the message edit code path to remove mobile push
    # notifications for users who are no longer mentioned following
    # the edit.  See #15428 for details.
    #
    # A perfect implementation would also support updating the message
    # in a sent notification if a message was edited to mention a
    # group rather than a user (or vice versa), though it is likely
    # not worth the effort to do such a change.
    if not message.is_stream_message():
        return

    remove_notify_users = prior_mention_user_ids - mentions_user_ids - stream_push_user_ids
    do_clear_mobile_push_notifications_for_ids(list(remove_notify_users), [message.id])


def do_clear_mobile_push_notifications_for_ids(
    user_profile_ids: List[int], message_ids: List[int]
) -> None:
    if len(message_ids) == 0:
        return

    # This function supports clearing notifications for several users
    # only for the message-edit use case where we'll have a single message_id.
    assert len(user_profile_ids) == 1 or len(message_ids) == 1

    messages_by_user = defaultdict(list)
    notifications_to_update = (
        UserMessage.objects.filter(
            message_id__in=message_ids,
            user_profile_id__in=user_profile_ids,
        )
        .extra(
            where=[UserMessage.where_active_push_notification()],
        )
        .values_list("user_profile_id", "message_id")
    )

    for user_id, message_id in notifications_to_update:
        messages_by_user[user_id].append(message_id)

    for user_profile_id, event_message_ids in messages_by_user.items():
        notice = {
            "type": "remove",
            "user_profile_id": user_profile_id,
            "message_ids": event_message_ids,
        }
        if settings.MOBILE_NOTIFICATIONS_SHARDS > 1:  # nocoverage
            shard_id = user_profile_id % settings.MOBILE_NOTIFICATIONS_SHARDS + 1
            queue_json_publish(f"missedmessage_mobile_notifications_shard{shard_id}", notice)
        else:
            queue_json_publish("missedmessage_mobile_notifications", notice)


def do_update_message_flags(
    user_profile: UserProfile, operation: str, flag: str, messages: List[int]
) -> int:
    valid_flags = [item for item in UserMessage.flags if item not in UserMessage.NON_API_FLAGS]
    if flag not in valid_flags:
        raise JsonableError(_("Invalid flag: '{flag}'").format(flag=flag))
    if flag in UserMessage.NON_EDITABLE_FLAGS:
        raise JsonableError(_("Flag not editable: '{flag}'").format(flag=flag))
    if operation not in ("add", "remove"):
        raise JsonableError(
            _("Invalid message flag operation: '{operation}'").format(operation=operation)
        )
    is_adding = operation == "add"
    flagattr = getattr(UserMessage.flags, flag)
    flag_target = flagattr if is_adding else 0

    with transaction.atomic(savepoint=False):
        if flag == "read" and not is_adding:
            # We have an invariant that all stream messages marked as
            # unread must be in streams the user is subscribed to.
            #
            # When marking as unread, we enforce this invariant by
            # ignoring any messages in streams the user is not
            # currently subscribed to.
            subscribed_recipient_ids = get_subscribed_stream_recipient_ids_for_user(user_profile)

            message_ids_in_unsubscribed_streams = set(
                # Uses index: zerver_message_pkey
                Message.objects.select_related("recipient")
                .filter(id__in=messages, recipient__type=Recipient.STREAM)
                .exclude(recipient_id__in=subscribed_recipient_ids)
                .values_list("id", flat=True)
            )

            messages = [
                message_id
                for message_id in messages
                if message_id not in message_ids_in_unsubscribed_streams
            ]

        ums = {
            um.message_id: um
            for um in UserMessage.select_for_update_query().filter(
                user_profile=user_profile, message_id__in=messages
            )
        }

        # Filter out rows that already have the desired flag.  We do
        # this here, rather than in the original database query,
        # because not all flags have database indexes and we want to
        # bound the cost of this operation.
        messages = [
            message_id
            for message_id in messages
            if (int(ums[message_id].flags) if message_id in ums else DEFAULT_HISTORICAL_FLAGS)
            & flagattr
            != flag_target
        ]
        count = len(messages)

        if DEFAULT_HISTORICAL_FLAGS & flagattr != flag_target:
            # When marking messages as read, creating "historical"
            # UserMessage rows would be a waste of storage, because
            # `flags.read | flags.historical` is exactly the flags we
            # simulate when processing a message for which a user has
            # access but no UserMessage row.
            #
            # Users can mutate flags for messages that don't have a
            # UserMessage yet.  Validate that the user is even allowed
            # to access these message_ids; if so, we will create
            # "historical" UserMessage rows for the messages in question.
            #
            # See create_historical_user_messages for a more detailed
            # explanation.
            historical_message_ids = set(messages) - set(ums.keys())
            historical_messages = bulk_access_messages(
                user_profile,
                list(
                    # Uses index: zerver_message_pkey
                    Message.objects.filter(id__in=historical_message_ids).prefetch_related(
                        "recipient"
                    )
                ),
            )
            if len(historical_messages) != len(historical_message_ids):
                raise JsonableError(_("Invalid message(s)"))

            create_historical_user_messages(
                user_id=user_profile.id,
                message_ids=list(historical_message_ids),
                flagattr=flagattr,
                flag_target=flag_target,
            )

        to_update = UserMessage.objects.filter(
            user_profile=user_profile, message_id__in=set(messages) & set(ums.keys())
        )
        if is_adding:
            to_update.update(flags=F("flags").bitor(flagattr))
        else:
            to_update.update(flags=F("flags").bitand(~flagattr))

    event = {
        "type": "update_message_flags",
        "op": operation,
        "operation": operation,
        "flag": flag,
        "messages": messages,
        "all": False,
    }

    if flag == "read" and not is_adding:
        # When removing the read flag (i.e. marking messages as
        # unread), extend the event with an additional object with
        # details on the messages required to update the client's
        # `unread_msgs` data structure.
        raw_unread_data = get_raw_unread_data(user_profile, messages)
        event["message_details"] = format_unread_message_details(user_profile.id, raw_unread_data)

    send_event(user_profile.realm, event, [user_profile.id])

    if flag == "read" and is_adding:
        event_time = timezone_now()
        do_clear_mobile_push_notifications_for_ids([user_profile.id], messages)

        do_increment_logging_stat(
            user_profile, COUNT_STATS["messages_read::hour"], None, event_time, increment=count
        )
        do_increment_logging_stat(
            user_profile,
            COUNT_STATS["messages_read_interactions::hour"],
            None,
            event_time,
            increment=min(1, count),
        )

    return count

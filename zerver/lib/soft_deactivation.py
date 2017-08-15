from __future__ import absolute_import

from collections import defaultdict
from django.db import transaction
from django.utils.timezone import now as timezone_now
from typing import DefaultDict, List

from zerver.models import UserProfile, UserMessage, RealmAuditLog, \
    Subscription, Message, Recipient

def filter_by_subscription_history(
        user_profile, all_stream_messages, all_stream_subscription_logs):
    # type: (UserProfile, DefaultDict[int, List[Message]], DefaultDict[int, List[RealmAuditLog]]) -> List[UserMessage]
    user_messages_to_insert = []  # type: List[UserMessage]

    def store_user_message_to_insert(message):
        # type: (Message) -> None
        message = UserMessage(user_profile=user_profile,
                              message_id=message['id'], flags=0)
        user_messages_to_insert.append(message)

    for (stream_id, stream_messages) in all_stream_messages.items():
        stream_subscription_logs = all_stream_subscription_logs[stream_id]

        for log_entry in stream_subscription_logs:
            if len(stream_messages) == 0:
                continue
            if log_entry.event_type == 'subscription_deactivated':
                for stream_message in stream_messages:
                    if stream_message['id'] <= log_entry.event_last_message_id:
                        store_user_message_to_insert(stream_message)
                    else:
                        break
            elif log_entry.event_type in ('subscription_activated',
                                          'subscription_created'):
                initial_msg_count = len(stream_messages)
                for i, stream_message in enumerate(stream_messages):
                    if stream_message['id'] > log_entry.event_last_message_id:
                        stream_messages = stream_messages[i:]
                        break
                final_msg_count = len(stream_messages)
                if initial_msg_count == final_msg_count:
                    if stream_messages[-1]['id'] <= log_entry.event_last_message_id:
                        stream_messages = []
            else:
                raise AssertionError('%s is not a Subscription Event.' % (log_entry.event_type))

        if len(stream_messages) > 0:
            # We do this check for last event since if the last subscription
            # event was a subscription_deactivated then we don't want to create
            # UserMessage rows for any of the remaining messages.
            if stream_subscription_logs[-1].event_type in (
                    'subscription_activated',
                    'subscription_created'):
                for stream_message in stream_messages:
                    store_user_message_to_insert(stream_message)
    return user_messages_to_insert

def add_missing_messages(user_profile):
    # type: (UserProfile) -> None
    all_stream_subs = list(Subscription.objects.select_related('recipient').filter(
        user_profile=user_profile,
        recipient__type=Recipient.STREAM).values('recipient', 'recipient__type_id'))

    # For Stream messages we need to check messages against data from
    # RealmAuditLog for visibility to user. So we fetch the subscription logs.
    stream_ids = [sub['recipient__type_id'] for sub in all_stream_subs]
    events = ['subscription_created', 'subscription_deactivated', 'subscription_activated']
    subscription_logs = list(RealmAuditLog.objects.select_related(
        'modified_stream').filter(
        modified_user=user_profile,
        modified_stream__id__in=stream_ids,
        event_type__in=events).order_by('event_last_message_id'))

    all_stream_subscription_logs = defaultdict(list)  # type: DefaultDict[int, List]
    for log in subscription_logs:
        all_stream_subscription_logs[log.modified_stream.id].append(log)

    recipient_ids = []
    for sub in all_stream_subs:
        stream_subscription_logs = all_stream_subscription_logs[sub['recipient__type_id']]
        if (stream_subscription_logs[-1].event_type == 'subscription_deactivated' and
                stream_subscription_logs[-1].event_last_message_id < user_profile.last_active_message_id):
            # We are going to short circuit this iteration as its no use
            # iterating since user unsubscribed before soft-deactivation
            continue
        recipient_ids.append(sub['recipient'])

    all_stream_msgs = list(Message.objects.select_related(
        'recipient').filter(
        recipient__id__in=recipient_ids,
        id__gt=user_profile.last_active_message_id).order_by('id').values(
        'id', 'recipient__type_id'))
    already_created_um_objs = list(UserMessage.objects.select_related(
        'message').filter(
        user_profile=user_profile,
        message__recipient__type=Recipient.STREAM,
        message__id__gt=user_profile.last_active_message_id).values(
        'message__id'))
    already_created_ums = set([obj['message__id'] for obj in already_created_um_objs])

    # Filter those messages for which UserMessage rows have been already created
    all_stream_msgs = [msg for msg in all_stream_msgs
                       if msg['id'] not in already_created_ums]

    stream_messages = defaultdict(list)  # type: DefaultDict[int, List]
    for msg in all_stream_msgs:
        stream_messages[msg['recipient__type_id']].append(msg)

    # Calling this function to filter out stream messages based upon
    # subscription logs and then store all UserMessage objects for bulk insert
    # This function does not perform any SQL related task and gets all the data
    # required for its operation in its params.
    user_messages_to_insert = filter_by_subscription_history(
        user_profile, stream_messages, all_stream_subscription_logs)

    # Doing a bulk create for all the UserMessage objects stored for creation.
    if len(user_messages_to_insert) > 0:
        UserMessage.objects.bulk_create(user_messages_to_insert)

def do_soft_deactivate_user(user_profile):
    # type: (UserProfile) -> None
    user_profile.last_active_message_id = UserMessage.objects.filter(
        user_profile=user_profile).order_by(
        '-message__id')[0].message_id
    user_profile.long_term_idle = True
    user_profile.save(update_fields=[
        'long_term_idle',
        'last_active_message_id'])

def do_soft_deactivate_users(users):
    # type: (List[UserProfile]) -> None
    with transaction.atomic():
        realm_logs = []
        for user in users:
            do_soft_deactivate_user(user)
            event_time = timezone_now()
            log = RealmAuditLog(
                realm=user.realm,
                modified_user=user,
                event_type='user_soft_deactivated',
                event_time=event_time
            )
            realm_logs.append(log)
        RealmAuditLog.objects.bulk_create(realm_logs)

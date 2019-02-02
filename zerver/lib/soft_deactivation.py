
from zerver.lib.logging_util import log_to_file
from collections import defaultdict
import logging
from django.db import transaction
from django.db.models import Max
from django.conf import settings
from django.utils.timezone import now as timezone_now
from typing import DefaultDict, List, Union, Any

from zerver.models import UserProfile, UserMessage, RealmAuditLog, \
    Subscription, Message, Recipient, UserActivity

logger = logging.getLogger("zulip.soft_deactivation")
log_to_file(logger, settings.SOFT_DEACTIVATION_LOG_PATH)

def filter_by_subscription_history(user_profile: UserProfile,
                                   all_stream_messages: DefaultDict[int, List[Message]],
                                   all_stream_subscription_logs: DefaultDict[int, List[RealmAuditLog]],
                                   ) -> List[UserMessage]:
    user_messages_to_insert = []  # type: List[UserMessage]

    def store_user_message_to_insert(message: Message) -> None:
        message = UserMessage(user_profile=user_profile,
                              message_id=message['id'], flags=0)
        user_messages_to_insert.append(message)

    for (stream_id, stream_messages) in all_stream_messages.items():
        stream_subscription_logs = all_stream_subscription_logs[stream_id]

        for log_entry in stream_subscription_logs:
            if len(stream_messages) == 0:
                continue
            if log_entry.event_type == RealmAuditLog.SUBSCRIPTION_DEACTIVATED:
                for stream_message in stream_messages:
                    if stream_message['id'] <= log_entry.event_last_message_id:
                        store_user_message_to_insert(stream_message)
                    else:
                        break
            elif log_entry.event_type in (RealmAuditLog.SUBSCRIPTION_ACTIVATED,
                                          RealmAuditLog.SUBSCRIPTION_CREATED):
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
                    RealmAuditLog.SUBSCRIPTION_ACTIVATED,
                    RealmAuditLog.SUBSCRIPTION_CREATED):
                for stream_message in stream_messages:
                    store_user_message_to_insert(stream_message)
    return user_messages_to_insert

def add_missing_messages(user_profile: UserProfile) -> None:
    """This function takes a soft-deactivated user, and computes and adds
    to the database any UserMessage rows that were not created while
    the user was soft-deactivated.  The end result is that from the
    perspective of the message database, it should be impossible to
    tell that the user was soft-deactivated at all.

    At a high level, the algorithm is as follows:

    * Find all the streams that the user was at any time a subscriber
      of when or after they were soft-deactivated (`recipient_ids`
      below).

    * Find all the messages sent to those streams since the user was
      soft-deactivated.  This will be a superset of the target
      UserMessages we need to create in two ways: (1) some UserMessage
      rows will have already been created in do_send_messages because
      the user had a nonzero set of flags (the fact that we do so in
      do_send_messages simplifies things considerably, since it means
      we don't need to inspect message content to look for things like
      mentions here), and (2) the user might not have been subscribed
      to all of the streams in recipient_ids for the entire time
      window.

    * Correct the list from the previous state by excluding those with
      existing UserMessage rows.

    * Correct the list from the previous state by excluding those
      where the user wasn't subscribed at the time, using the
      RealmAuditLog data to determine exactly when the user was
      subscribed/unsubscribed.

    * Create the UserMessage rows.

    """
    assert user_profile.last_active_message_id is not None
    all_stream_subs = list(Subscription.objects.select_related('recipient').filter(
        user_profile=user_profile,
        recipient__type=Recipient.STREAM).values('recipient', 'recipient__type_id'))

    # For Stream messages we need to check messages against data from
    # RealmAuditLog for visibility to user. So we fetch the subscription logs.
    stream_ids = [sub['recipient__type_id'] for sub in all_stream_subs]
    events = [RealmAuditLog.SUBSCRIPTION_CREATED, RealmAuditLog.SUBSCRIPTION_DEACTIVATED,
              RealmAuditLog.SUBSCRIPTION_ACTIVATED]
    subscription_logs = list(RealmAuditLog.objects.select_related(
        'modified_stream').filter(
        modified_user=user_profile,
        modified_stream__id__in=stream_ids,
        event_type__in=events).order_by('event_last_message_id'))

    all_stream_subscription_logs = defaultdict(list)  # type: DefaultDict[int, List[RealmAuditLog]]
    for log in subscription_logs:
        all_stream_subscription_logs[log.modified_stream.id].append(log)

    recipient_ids = []
    for sub in all_stream_subs:
        stream_subscription_logs = all_stream_subscription_logs[sub['recipient__type_id']]
        if stream_subscription_logs[-1].event_type == RealmAuditLog.SUBSCRIPTION_DEACTIVATED:
            assert stream_subscription_logs[-1].event_last_message_id is not None
            if stream_subscription_logs[-1].event_last_message_id <= user_profile.last_active_message_id:
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

    stream_messages = defaultdict(list)  # type: DefaultDict[int, List[Message]]
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

def do_soft_deactivate_user(user_profile: UserProfile) -> None:
    try:
        user_profile.last_active_message_id = UserMessage.objects.filter(
            user_profile=user_profile).order_by(
                '-message__id')[0].message_id
    except IndexError:  # nocoverage
        # In the unlikely event that a user somehow has never received
        # a message, we just use the overall max message ID.
        user_profile.last_active_message_id = Message.objects.max().id
    user_profile.long_term_idle = True
    user_profile.save(update_fields=[
        'long_term_idle',
        'last_active_message_id'])
    logger.info('Soft Deactivated user %s (%s)' %
                (user_profile.id, user_profile.email))

def do_soft_deactivate_users(users: List[UserProfile]) -> List[UserProfile]:
    BATCH_SIZE = 100
    users_soft_deactivated = []
    while True:
        (user_batch, users) = (users[0:BATCH_SIZE], users[BATCH_SIZE:])
        if len(user_batch) == 0:
            break
        with transaction.atomic():
            realm_logs = []
            for user in user_batch:
                do_soft_deactivate_user(user)
                event_time = timezone_now()
                log = RealmAuditLog(
                    realm=user.realm,
                    modified_user=user,
                    event_type=RealmAuditLog.USER_SOFT_DEACTIVATED,
                    event_time=event_time
                )
                realm_logs.append(log)
                users_soft_deactivated.append(user)
            RealmAuditLog.objects.bulk_create(realm_logs)

        logging.info("Soft-deactivated batch of %s users; %s remain to process" %
                     (len(user_batch), len(users)))

    return users_soft_deactivated

def maybe_catch_up_soft_deactivated_user(user_profile: UserProfile) -> Union[UserProfile, None]:
    if user_profile.long_term_idle:
        add_missing_messages(user_profile)
        user_profile.long_term_idle = False
        user_profile.save(update_fields=['long_term_idle'])
        RealmAuditLog.objects.create(
            realm=user_profile.realm,
            modified_user=user_profile,
            event_type=RealmAuditLog.USER_SOFT_ACTIVATED,
            event_time=timezone_now()
        )
        logger.info('Soft Reactivated user %s (%s)' %
                    (user_profile.id, user_profile.email))
        return user_profile
    return None

def get_users_for_soft_deactivation(inactive_for_days: int, filter_kwargs: Any) -> List[UserProfile]:
    users_activity = list(UserActivity.objects.filter(
        user_profile__is_active=True,
        user_profile__is_bot=False,
        user_profile__long_term_idle=False,
        **filter_kwargs).values('user_profile_id').annotate(
        last_visit=Max('last_visit')))
    user_ids_to_deactivate = []
    today = timezone_now()
    for user_activity in users_activity:
        if (today - user_activity['last_visit']).days > inactive_for_days:
            user_ids_to_deactivate.append(user_activity['user_profile_id'])
    users_to_deactivate = list(UserProfile.objects.filter(
        id__in=user_ids_to_deactivate))
    return users_to_deactivate

def do_soft_activate_users(users: List[UserProfile]) -> List[UserProfile]:
    users_soft_activated = []
    for user_profile in users:
        user_activated = maybe_catch_up_soft_deactivated_user(user_profile)
        if user_activated:
            users_soft_activated.append(user_activated)
    return users_soft_activated

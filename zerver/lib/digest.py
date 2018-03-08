from typing import Any, Callable, Dict, Iterable, List, Set, Tuple, Text

from collections import defaultdict
import datetime
import logging
import pytz

from django.db.models import Q, QuerySet
from django.template import loader
from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.lib.notifications import build_message_list, encode_stream, \
    one_click_unsubscribe_link
from zerver.lib.send_email import send_future_email, FromAddress
from zerver.models import UserProfile, UserMessage, Recipient, Stream, \
    Subscription, UserActivity, get_active_streams, get_user_profile_by_id, \
    Realm
from zerver.context_processors import common_context
from zerver.lib.queue import queue_json_publish
from zerver.lib.logging_util import log_to_file

logger = logging.getLogger(__name__)
log_to_file(logger, settings.DIGEST_LOG_PATH)

VALID_DIGEST_DAY = 1  # Tuesdays
DIGEST_CUTOFF = 5

# Digests accumulate 4 types of interesting traffic for a user:
# 1. Missed PMs
# 2. New streams
# 3. New users
# 4. Interesting stream traffic, as determined by the longest and most
#    diversely comment upon topics.

def inactive_since(user_profile: UserProfile, cutoff: datetime.datetime) -> bool:
    # Hasn't used the app in the last DIGEST_CUTOFF (5) days.
    most_recent_visit = [row.last_visit for row in
                         UserActivity.objects.filter(
                             user_profile=user_profile)]

    if not most_recent_visit:
        # This person has never used the app.
        return True

    last_visit = max(most_recent_visit)
    return last_visit < cutoff

def should_process_digest(realm_str: str) -> bool:
    if realm_str in settings.SYSTEM_ONLY_REALMS:
        # Don't try to send emails to system-only realms
        return False
    return True

# Changes to this should also be reflected in
# zerver/worker/queue_processors.py:DigestWorker.consume()
def queue_digest_recipient(user_profile: UserProfile, cutoff: datetime.datetime) -> None:
    # Convert cutoff to epoch seconds for transit.
    event = {"user_profile_id": user_profile.id,
             "cutoff": cutoff.strftime('%s')}
    queue_json_publish("digest_emails", event)

def enqueue_emails(cutoff: datetime.datetime) -> None:
    if not settings.SEND_DIGEST_EMAILS:
        return

    if timezone_now().weekday() != VALID_DIGEST_DAY:
        return

    for realm in Realm.objects.filter(deactivated=False, show_digest_email=True):
        if not should_process_digest(realm.string_id):
            continue

        user_profiles = UserProfile.objects.filter(
            realm=realm, is_active=True, is_bot=False, enable_digest_emails=True)

        for user_profile in user_profiles:
            if inactive_since(user_profile, cutoff):
                queue_digest_recipient(user_profile, cutoff)
                logger.info("%s is inactive, queuing for potential digest" % (
                    user_profile.email,))

def gather_hot_conversations(user_profile: UserProfile, stream_messages: QuerySet) -> List[Dict[str, Any]]:
    # Gather stream conversations of 2 types:
    # 1. long conversations
    # 2. conversations where many different people participated
    #
    # Returns a list of dictionaries containing the templating
    # information for each hot conversation.

    conversation_length = defaultdict(int)  # type: Dict[Tuple[int, Text], int]
    conversation_diversity = defaultdict(set)  # type: Dict[Tuple[int, Text], Set[Text]]
    for user_message in stream_messages:
        if not user_message.message.sent_by_human():
            # Don't include automated messages in the count.
            continue

        key = (user_message.message.recipient.type_id,
               user_message.message.subject)
        conversation_diversity[key].add(
            user_message.message.sender.full_name)
        conversation_length[key] += 1

    diversity_list = list(conversation_diversity.items())
    diversity_list.sort(key=lambda entry: len(entry[1]), reverse=True)

    length_list = list(conversation_length.items())
    length_list.sort(key=lambda entry: entry[1], reverse=True)

    # Get up to the 4 best conversations from the diversity list
    # and length list, filtering out overlapping conversations.
    hot_conversations = [elt[0] for elt in diversity_list[:2]]
    for candidate, _ in length_list:
        if candidate not in hot_conversations:
            hot_conversations.append(candidate)
        if len(hot_conversations) >= 4:
            break

    # There was so much overlap between the diversity and length lists that we
    # still have < 4 conversations. Try to use remaining diversity items to pad
    # out the hot conversations.
    num_convos = len(hot_conversations)
    if num_convos < 4:
        hot_conversations.extend([elt[0] for elt in diversity_list[num_convos:4]])

    hot_conversation_render_payloads = []
    for h in hot_conversations:
        stream_id, subject = h
        users = list(conversation_diversity[h])
        count = conversation_length[h]

        # We'll display up to 2 messages from the conversation.
        first_few_messages = [user_message.message for user_message in
                              stream_messages.filter(
                                  message__recipient__type_id=stream_id,
                                  message__subject=subject)[:2]]

        teaser_data = {"participants": users,
                       "count": count - len(first_few_messages),
                       "first_few_messages": build_message_list(
                           user_profile, first_few_messages)}

        hot_conversation_render_payloads.append(teaser_data)
    return hot_conversation_render_payloads

def gather_new_users(user_profile: UserProfile, threshold: datetime.datetime) -> Tuple[int, List[Text]]:
    # Gather information on users in the realm who have recently
    # joined.
    if user_profile.realm.is_zephyr_mirror_realm:
        new_users = []  # type: List[UserProfile]
    else:
        new_users = list(UserProfile.objects.filter(
            realm=user_profile.realm, date_joined__gt=threshold,
            is_bot=False))
    user_names = [user.full_name for user in new_users]

    return len(user_names), user_names

def gather_new_streams(user_profile: UserProfile,
                       threshold: datetime.datetime) -> Tuple[int, Dict[str, List[Text]]]:
    if user_profile.realm.is_zephyr_mirror_realm:
        new_streams = []  # type: List[Stream]
    else:
        new_streams = list(get_active_streams(user_profile.realm).filter(
            invite_only=False, date_created__gt=threshold))

    base_url = "%s/#narrow/stream/" % (user_profile.realm.uri,)

    streams_html = []
    streams_plain = []

    for stream in new_streams:
        narrow_url = base_url + encode_stream(stream.id, stream.name)
        stream_link = "<a href='%s'>%s</a>" % (narrow_url, stream.name)
        streams_html.append(stream_link)
        streams_plain.append(stream.name)

    return len(new_streams), {"html": streams_html, "plain": streams_plain}

def enough_traffic(unread_pms: Text, hot_conversations: Text, new_streams: int, new_users: int) -> bool:
    if unread_pms or hot_conversations:
        # If you have any unread traffic, good enough.
        return True
    if new_streams and new_users:
        # If you somehow don't have any traffic but your realm did get
        # new streams and users, good enough.
        return True
    return False

def handle_digest_email(user_profile_id: int, cutoff: float) -> None:
    user_profile = get_user_profile_by_id(user_profile_id)

    # We are disabling digest emails for soft deactivated users for the time.
    # TODO: Find an elegant way to generate digest emails for these users.
    if user_profile.long_term_idle:
        return None

    # Convert from epoch seconds to a datetime object.
    cutoff_date = datetime.datetime.fromtimestamp(int(cutoff), tz=pytz.utc)

    all_messages = UserMessage.objects.filter(
        user_profile=user_profile,
        message__pub_date__gt=cutoff_date).order_by("message__pub_date")

    context = common_context(user_profile)

    # Start building email template data.
    context.update({
        'realm_name': user_profile.realm.name,
        'name': user_profile.full_name,
        'unsubscribe_link': one_click_unsubscribe_link(user_profile, "digest")
    })

    # Gather recent missed PMs, re-using the missed PM email logic.
    # You can't have an unread message that you sent, but when testing
    # this causes confusion so filter your messages out.
    pms = all_messages.filter(
        ~Q(message__recipient__type=Recipient.STREAM) &
        ~Q(message__sender=user_profile))

    # Show up to 4 missed PMs.
    pms_limit = 4

    context['unread_pms'] = build_message_list(
        user_profile, [pm.message for pm in pms[:pms_limit]])
    context['remaining_unread_pms_count'] = min(0, len(pms) - pms_limit)

    home_view_recipients = [sub.recipient for sub in
                            Subscription.objects.filter(
                                user_profile=user_profile,
                                active=True,
                                in_home_view=True)]

    stream_messages = all_messages.filter(
        message__recipient__type=Recipient.STREAM,
        message__recipient__in=home_view_recipients)

    # Gather hot conversations.
    context["hot_conversations"] = gather_hot_conversations(
        user_profile, stream_messages)

    # Gather new streams.
    new_streams_count, new_streams = gather_new_streams(
        user_profile, cutoff_date)
    context["new_streams"] = new_streams
    context["new_streams_count"] = new_streams_count

    # Gather users who signed up recently.
    new_users_count, new_users = gather_new_users(
        user_profile, cutoff_date)
    context["new_users"] = new_users

    # We don't want to send emails containing almost no information.
    if enough_traffic(context["unread_pms"], context["hot_conversations"],
                      new_streams_count, new_users_count):
        logger.info("Sending digest email for %s" % (user_profile.email,))
        # Send now, as a ScheduledEmail
        send_future_email('zerver/emails/digest', user_profile.realm, to_user_id=user_profile.id,
                          from_name="Zulip Digest", from_address=FromAddress.NOREPLY,
                          context=context)

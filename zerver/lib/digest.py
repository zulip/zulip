from typing import Any, Dict, List, Set, Tuple, Union

from collections import defaultdict
import datetime
import logging
import pytz

from django.conf import settings
from django.utils.timezone import now as timezone_now

from confirmation.models import one_click_unsubscribe_link
from zerver.lib.email_notifications import build_message_list
from zerver.lib.send_email import send_future_email, FromAddress
from zerver.lib.url_encoding import encode_stream
from zerver.models import UserProfile, Recipient, Subscription, UserActivity, \
    get_active_streams, get_user_profile_by_id, Realm, Message, RealmAuditLog
from zerver.context_processors import common_context
from zerver.lib.queue import queue_json_publish
from zerver.lib.logging_util import log_to_file

logger = logging.getLogger(__name__)
log_to_file(logger, settings.DIGEST_LOG_PATH)

DIGEST_CUTOFF = 5

# Digests accumulate 2 types of interesting traffic for a user:
# 1. New streams
# 2. Interesting stream traffic, as determined by the longest and most
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

    weekday = timezone_now().weekday()
    for realm in Realm.objects.filter(deactivated=False, digest_emails_enabled=True, digest_weekday=weekday):
        if not should_process_digest(realm.string_id):
            continue

        user_profiles = UserProfile.objects.filter(
            realm=realm, is_active=True, is_bot=False, enable_digest_emails=True)

        for user_profile in user_profiles:
            if inactive_since(user_profile, cutoff):
                queue_digest_recipient(user_profile, cutoff)
                logger.info("User %s is inactive, queuing for potential digest" % (
                    user_profile.id,))

def gather_hot_conversations(user_profile: UserProfile, messages: List[Message]) -> List[Dict[str, Any]]:
    # Gather stream conversations of 2 types:
    # 1. long conversations
    # 2. conversations where many different people participated
    #
    # Returns a list of dictionaries containing the templating
    # information for each hot conversation.

    conversation_length = defaultdict(int)  # type: Dict[Tuple[int, str], int]
    conversation_messages = defaultdict(list)  # type: Dict[Tuple[int, str], List[Message]]
    conversation_diversity = defaultdict(set)  # type: Dict[Tuple[int, str], Set[str]]
    for message in messages:
        key = (message.recipient.type_id,
               message.topic_name())

        conversation_messages[key].append(message)

        if not message.sent_by_human():
            # Don't include automated messages in the count.
            continue

        conversation_diversity[key].add(
            message.sender.full_name)
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
        users = list(conversation_diversity[h])
        count = conversation_length[h]
        messages = conversation_messages[h]

        # We'll display up to 2 messages from the conversation.
        first_few_messages = messages[:2]

        teaser_data = {"participants": users,
                       "count": count - len(first_few_messages),
                       "first_few_messages": build_message_list(
                           user_profile, first_few_messages)}

        hot_conversation_render_payloads.append(teaser_data)
    return hot_conversation_render_payloads

def gather_new_streams(user_profile: UserProfile,
                       threshold: datetime.datetime) -> Tuple[int, Dict[str, List[str]]]:
    if user_profile.can_access_public_streams():
        new_streams = list(get_active_streams(user_profile.realm).filter(
            invite_only=False, date_created__gt=threshold))
    else:
        new_streams = []

    base_url = "%s/#narrow/stream/" % (user_profile.realm.uri,)

    streams_html = []
    streams_plain = []

    for stream in new_streams:
        narrow_url = base_url + encode_stream(stream.id, stream.name)
        stream_link = "<a href='%s'>%s</a>" % (narrow_url, stream.name)
        streams_html.append(stream_link)
        streams_plain.append(stream.name)

    return len(new_streams), {"html": streams_html, "plain": streams_plain}

def enough_traffic(hot_conversations: str, new_streams: int) -> bool:
    return bool(hot_conversations or new_streams)

def handle_digest_email(user_profile_id: int, cutoff: float,
                        render_to_web: bool = False) -> Union[None, Dict[str, Any]]:
    user_profile = get_user_profile_by_id(user_profile_id)

    # Convert from epoch seconds to a datetime object.
    cutoff_date = datetime.datetime.fromtimestamp(int(cutoff), tz=pytz.utc)

    context = common_context(user_profile)

    # Start building email template data.
    context.update({
        'unsubscribe_link': one_click_unsubscribe_link(user_profile, "digest")
    })

    home_view_streams = Subscription.objects.filter(
        user_profile=user_profile,
        recipient__type=Recipient.STREAM,
        active=True,
        is_muted=False).values_list('recipient__type_id', flat=True)

    if not user_profile.long_term_idle:
        stream_ids = home_view_streams
    else:
        stream_ids = exclude_subscription_modified_streams(user_profile, home_view_streams, cutoff_date)

    # Fetch list of all messages sent after cutoff_date where the user is subscribed
    messages = Message.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=stream_ids,
        date_sent__gt=cutoff_date).select_related('recipient', 'sender', 'sending_client')

    # Gather hot conversations.
    context["hot_conversations"] = gather_hot_conversations(
        user_profile, messages)

    # Gather new streams.
    new_streams_count, new_streams = gather_new_streams(
        user_profile, cutoff_date)
    context["new_streams"] = new_streams
    context["new_streams_count"] = new_streams_count

    # TODO: Set has_preheader if we want to include a preheader.

    if render_to_web:
        return context

    # We don't want to send emails containing almost no information.
    if enough_traffic(context["hot_conversations"], new_streams_count):
        logger.info("Sending digest email for user %s" % (user_profile.id,))
        # Send now, as a ScheduledEmail
        send_future_email('zerver/emails/digest', user_profile.realm, to_user_ids=[user_profile.id],
                          from_name="Zulip Digest", from_address=FromAddress.NOREPLY, context=context)
    return None

def exclude_subscription_modified_streams(user_profile: UserProfile,
                                          stream_ids: List[int],
                                          cutoff_date: datetime.datetime) -> List[int]:
    """Exclude streams from given list where users' subscription was modified."""

    events = [
        RealmAuditLog.SUBSCRIPTION_CREATED,
        RealmAuditLog.SUBSCRIPTION_ACTIVATED,
        RealmAuditLog.SUBSCRIPTION_DEACTIVATED
    ]

    # Streams where the user's subscription was changed
    modified_streams = RealmAuditLog.objects.filter(
        realm=user_profile.realm,
        modified_user=user_profile,
        event_time__gt=cutoff_date,
        event_type__in=events).values_list('modified_stream_id', flat=True)

    return list(set(stream_ids) - set(modified_streams))

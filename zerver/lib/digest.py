from __future__ import absolute_import
from typing import Any, Callable, Iterable, Tuple

from collections import defaultdict
import datetime
import six
from six import text_type

from django.db.models import Q, QuerySet
from django.template import loader
from django.conf import settings

from zerver.lib.notifications import build_message_list, hashchange_encode, \
    send_future_email, one_click_unsubscribe_link
from zerver.models import UserProfile, UserMessage, Recipient, Stream, \
    Subscription, get_active_streams

import logging

log_format = "%(asctime)s: %(message)s"
logging.basicConfig(format=log_format)

formatter = logging.Formatter(log_format)
file_handler = logging.FileHandler(settings.DIGEST_LOG_PATH)
file_handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

# Digests accumulate 4 types of interesting traffic for a user:
# 1. Missed PMs
# 2. New streams
# 3. New users
# 4. Interesting stream traffic, as determined by the longest and most
#    diversely comment upon topics.

def gather_hot_conversations(user_profile, stream_messages):
    # type: (UserProfile, QuerySet) -> List[Dict[str, Any]]
    # Gather stream conversations of 2 types:
    # 1. long conversations
    # 2. conversations where many different people participated
    #
    # Returns a list of dictionaries containing the templating
    # information for each hot conversation.

    conversation_length = defaultdict(int) # type: Dict[Tuple[int, text_type], int]
    conversation_diversity = defaultdict(set) # type: Dict[Tuple[int, text_type], Set[text_type]]
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
        first_few_messages = [user_message.message for user_message in \
                                  stream_messages.filter(
                message__recipient__type_id=stream_id,
                message__subject=subject)[:2]]

        teaser_data = {"participants": users,
                       "count": count - len(first_few_messages),
                       "first_few_messages": build_message_list(
                user_profile, first_few_messages)}

        hot_conversation_render_payloads.append(teaser_data)
    return hot_conversation_render_payloads

def gather_new_users(user_profile, threshold):
    # type: (UserProfile, datetime.datetime) -> Tuple[int, List[text_type]]
    # Gather information on users in the realm who have recently
    # joined.
    if user_profile.realm.is_zephyr_mirror_realm:
        new_users = [] # type: List[UserProfile]
    else:
        new_users = list(UserProfile.objects.filter(
                realm=user_profile.realm, date_joined__gt=threshold,
                is_bot=False))
    user_names = [user.full_name for user in new_users]

    return len(user_names), user_names

def gather_new_streams(user_profile, threshold):
    # type: (UserProfile, datetime.datetime) -> Tuple[int, Dict[str, List[text_type]]]
    if user_profile.realm.is_zephyr_mirror_realm:
        new_streams = [] # type: List[Stream]
    else:
        new_streams = list(get_active_streams(user_profile.realm).filter(
                invite_only=False, date_created__gt=threshold))

    base_url = u"https://%s/#narrow/stream/" % (settings.EXTERNAL_HOST,)

    streams_html = []
    streams_plain = []

    for stream in new_streams:
        narrow_url = base_url + hashchange_encode(stream.name)
        stream_link = u"<a href='%s'>%s</a>" % (narrow_url, stream.name)
        streams_html.append(stream_link)
        streams_plain.append(stream.name)

    return len(new_streams), {"html": streams_html, "plain": streams_plain}

def enough_traffic(unread_pms, hot_conversations, new_streams, new_users):
    # type: (text_type, text_type, int, int) -> bool
    if unread_pms or hot_conversations:
        # If you have any unread traffic, good enough.
        return True
    if new_streams and new_users:
        # If you somehow don't have any traffic but your realm did get
        # new streams and users, good enough.
        return True
    return False

def send_digest_email(user_profile, html_content, text_content):
    # type: (UserProfile, text_type, text_type) -> None
    recipients = [{'email': user_profile.email, 'name': user_profile.full_name}]
    subject = "While you've been gone - Zulip"
    sender = {'email': settings.NOREPLY_EMAIL_ADDRESS, 'name': 'Zulip'}

    # Send now, through Mandrill.
    send_future_email(recipients, html_content, text_content, subject,
                      delay=datetime.timedelta(0), sender=sender,
                      tags=["digest-emails"])

def handle_digest_email(user_profile_id, cutoff):
    # type: (int, int) -> None
    user_profile=UserProfile.objects.get(id=user_profile_id)
    # Convert from epoch seconds to a datetime object.
    cutoff_date = datetime.datetime.utcfromtimestamp(int(cutoff))

    all_messages = UserMessage.objects.filter(
        user_profile=user_profile,
        message__pub_date__gt=cutoff_date).order_by("message__pub_date")

    # Start building email template data.
    template_payload = {
        'name': user_profile.full_name,
        'external_host': settings.EXTERNAL_HOST,
        'external_uri_scheme': settings.EXTERNAL_URI_SCHEME,
        'server_uri': settings.SERVER_URI,
        'realm_uri': user_profile.realm.uri,
        'unsubscribe_link': one_click_unsubscribe_link(user_profile, "digest")
        } # type: Dict[str, Any]

    # Gather recent missed PMs, re-using the missed PM email logic.
    # You can't have an unread message that you sent, but when testing
    # this causes confusion so filter your messages out.
    pms = all_messages.filter(
        ~Q(message__recipient__type=Recipient.STREAM) & \
             ~Q(message__sender=user_profile))

    # Show up to 4 missed PMs.
    pms_limit = 4

    template_payload['unread_pms'] = build_message_list(
        user_profile, [pm.message for pm in pms[:pms_limit]])
    template_payload['remaining_unread_pms_count'] = min(0, len(pms) - pms_limit)

    home_view_recipients = [sub.recipient for sub in \
                                Subscription.objects.filter(
            user_profile=user_profile, active=True, in_home_view=True)]

    stream_messages = all_messages.filter(
        message__recipient__type=Recipient.STREAM,
        message__recipient__in=home_view_recipients)

    # Gather hot conversations.
    template_payload["hot_conversations"] = gather_hot_conversations(
        user_profile, stream_messages)

    # Gather new streams.
    new_streams_count, new_streams = gather_new_streams(
        user_profile, cutoff_date)
    template_payload["new_streams"] = new_streams
    template_payload["new_streams_count"] = new_streams_count

    # Gather users who signed up recently.
    new_users_count, new_users = gather_new_users(
        user_profile, cutoff_date)
    template_payload["new_users"] = new_users

    text_content = loader.render_to_string(
        'zerver/emails/digest/digest_email.txt', template_payload)
    html_content = loader.render_to_string(
        'zerver/emails/digest/digest_email_html.txt', template_payload)

    # We don't want to send emails containing almost no information.
    if enough_traffic(template_payload["unread_pms"],
                      template_payload["hot_conversations"],
                      new_streams_count, new_users_count):
        logger.info("Sending digest email for %s" % (user_profile.email,))
        send_digest_email(user_profile, html_content, text_content)

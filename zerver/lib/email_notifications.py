# See https://zulip.readthedocs.io/en/latest/subsystems/notifications.html

import logging
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from email.headerregistry import Address
from typing import Any, Dict, List, Optional, Tuple, Union

import lxml.html
import zoneinfo
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth import get_backends
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language
from lxml.html import builder as e

from confirmation.models import one_click_unsubscribe_link
from zerver.lib.display_recipient import get_display_recipient
from zerver.lib.markdown.fenced_code import FENCE_RE
from zerver.lib.message import bulk_access_messages
from zerver.lib.notification_data import get_mentioned_user_group
from zerver.lib.queue import queue_json_publish
from zerver.lib.send_email import FromAddress, send_future_email
from zerver.lib.soft_deactivation import soft_reactivate_if_personal_notification
from zerver.lib.tex import change_katex_to_raw_latex
from zerver.lib.timezone import canonicalize_timezone
from zerver.lib.topic import get_topic_resolution_and_bare_name
from zerver.lib.url_encoding import (
    huddle_narrow_url,
    personal_narrow_url,
    stream_narrow_url,
    topic_narrow_url,
)
from zerver.models import Message, Realm, Recipient, Stream, UserMessage, UserProfile
from zerver.models.messages import get_context_for_message
from zerver.models.scheduled_jobs import NotificationTriggers
from zerver.models.users import get_user_profile_by_id

logger = logging.getLogger(__name__)


def relative_to_full_url(fragment: lxml.html.HtmlElement, base_url: str) -> None:
    # We handle narrow URLs separately because of two reasons:
    # 1: 'lxml' seems to be having an issue in dealing with URLs that begin
    # `#` due to which it doesn't add a `/` before joining the base_url to
    # the relative URL.
    # 2: We also need to update the title attribute in the narrow links which
    # is not possible with `make_links_absolute()`.
    for link_info in fragment.iterlinks():
        elem, attrib, link, pos = link_info
        match = re.match(r"/?#narrow/", link)
        if match is not None:
            link = re.sub(r"^/?#narrow/", base_url + "/#narrow/", link)
            elem.set(attrib, link)
            # Only manually linked narrow URLs have title attribute set.
            if elem.get("title") is not None:
                elem.set("title", link)

    # Because we were parsed with fragment_fromstring, we are
    # guaranteed there is a top-level <div>, and the original
    # top-level contents are within that.
    if len(fragment) == 1 and fragment[0].get("class") == "message_inline_image":
        # The next block handles most inline images, but for messages
        # where the entire Markdown input was just the URL of an image
        # (i.e. the entire body is a message_inline_image object), the
        # entire message body will be that image element; here, we need a
        # more drastic edit to the content.
        inner = fragment[0]
        image_link = inner.find("a").get("href")
        image_title = inner.find("a").get("title")
        title_attr = {} if image_title is None else {"title": image_title}
        inner.clear()
        inner.tag = "p"
        inner.append(e.A(image_link, href=image_link, target="_blank", **title_attr))
    else:
        # Inline images can't be displayed in the emails as the request
        # from the mail server can't be authenticated because it has no
        # user_profile object linked to it. So we scrub the inline image
        # container.
        inline_image_containers = fragment.find_class("message_inline_image")
        for container in inline_image_containers:
            container.drop_tree()

    fragment.make_links_absolute(base_url)


def fix_emojis(fragment: lxml.html.HtmlElement, emojiset: str) -> None:
    def make_emoji_img_elem(emoji_span_elem: lxml.html.HtmlElement) -> Dict[str, Any]:
        # Convert the emoji spans to img tags.
        classes = emoji_span_elem.get("class")
        match = re.search(r"emoji-(?P<emoji_code>\S+)", classes)
        # re.search is capable of returning None,
        # but since the parent function should only be called with a valid css element
        # we assert that it does not.
        assert match is not None
        emoji_code = match.group("emoji_code")
        emoji_name = emoji_span_elem.get("title")
        alt_code = emoji_span_elem.text
        # We intentionally do not use staticfiles_storage.url here, so
        # that we don't get any hashed version -- we want a path which
        # may give us content which changes over time, but one which
        # is guaranteed to keep working even if the prod-static
        # directory is cleaned out (or a new server is rotated in
        # which does not have historical content with old hashed
        # filenames).
        image_url = f"{settings.STATIC_URL}generated/emoji/images-{emojiset}-64/{emoji_code}.png"
        img_elem = e.IMG(alt=alt_code, src=image_url, title=emoji_name, style="height: 20px;")
        img_elem.tail = emoji_span_elem.tail
        return img_elem

    for elem in fragment.cssselect("span.emoji"):
        parent = elem.getparent()
        img_elem = make_emoji_img_elem(elem)
        parent.replace(elem, img_elem)

    for realm_emoji in fragment.cssselect(".emoji"):
        del realm_emoji.attrib["class"]
        realm_emoji.set("style", "height: 20px;")


def fix_spoilers_in_html(fragment: lxml.html.HtmlElement, language: str) -> None:
    with override_language(language):
        spoiler_title: str = _("Open Zulip to see the spoiler content")
    spoilers = fragment.find_class("spoiler-block")
    for spoiler in spoilers:
        header = spoiler.find_class("spoiler-header")[0]
        spoiler_content = spoiler.find_class("spoiler-content")[0]
        header_content = header.find("p")
        if header_content is None:
            # Create a new element to append the spoiler to)
            header_content = e.P()
            header.append(header_content)
        else:
            # Add a space.
            rear = header_content[-1] if len(header_content) else header_content
            rear.tail = (rear.tail or "") + " "
        span_elem = e.SPAN(f"({spoiler_title})", **e.CLASS("spoiler-title"), title=spoiler_title)
        header_content.append(span_elem)
        header.drop_tag()
        spoiler_content.drop_tree()


def fix_spoilers_in_text(content: str, language: str) -> str:
    with override_language(language):
        spoiler_title: str = _("Open Zulip to see the spoiler content")
    lines = content.split("\n")
    output = []
    open_fence = None
    for line in lines:
        m = FENCE_RE.match(line)
        if m:
            fence = m.group("fence")
            lang: Optional[str] = m.group("lang")
            if lang == "spoiler":
                open_fence = fence
                output.append(line)
                output.append(f"({spoiler_title})")
            elif fence == open_fence:
                open_fence = None
                output.append(line)
        elif not open_fence:
            output.append(line)
    return "\n".join(output)


def add_quote_prefix_in_text(content: str) -> str:
    """
    We add quote prefix ">" to each line of the message in plain text
    format, such that email clients render the message as quote.
    """
    lines = content.split("\n")
    output = []
    for line in lines:
        quoted_line = f"> {line}"
        output.append(quoted_line)
    return "\n".join(output)


def build_message_list(
    user: UserProfile,
    messages: List[Message],
    stream_id_map: Optional[Dict[int, Stream]] = None,  # only needs id, name
) -> List[Dict[str, Any]]:
    """
    Builds the message list object for the message notification email template.
    The messages are collapsed into per-recipient and per-sender blocks, like
    our web interface
    """
    messages_to_render: List[Dict[str, Any]] = []

    def sender_string(message: Message) -> str:
        if message.recipient.type in (Recipient.STREAM, Recipient.DIRECT_MESSAGE_GROUP):
            return message.sender.full_name
        else:
            return ""

    def fix_plaintext_image_urls(content: str) -> str:
        # Replace image URLs in plaintext content of the form
        #     [image name](image url)
        # with a simple hyperlink.
        return re.sub(r"\[(\S*)\]\((\S*)\)", r"\2", content)

    def prepend_sender_to_message(
        message_plain: str, message_html: str, sender: str
    ) -> Tuple[str, str]:
        message_plain = f"{sender}:\n{message_plain}"
        message_soup = BeautifulSoup(message_html, "html.parser")
        sender_name_soup = BeautifulSoup(f"<b>{sender}</b>: ", "html.parser")
        first_tag = message_soup.find()
        if first_tag and first_tag.name == "div":
            first_tag = first_tag.find()
        if first_tag and first_tag.name == "p":
            first_tag.insert(0, sender_name_soup)
        else:
            message_soup.insert(0, sender_name_soup)
        return message_plain, str(message_soup)

    def build_message_payload(message: Message, sender: Optional[str] = None) -> Dict[str, str]:
        plain = message.content
        plain = fix_plaintext_image_urls(plain)
        # There's a small chance of colliding with non-Zulip URLs containing
        # "/user_uploads/", but we don't have much information about the
        # structure of the URL to leverage. We can't use `relative_to_full_url()`
        # function here because it uses a stricter regex which will not work for
        # plain text.
        plain = re.sub(r"/user_uploads/(\S*)", user.realm.uri + r"/user_uploads/\1", plain)
        plain = fix_spoilers_in_text(plain, user.default_language)
        plain = add_quote_prefix_in_text(plain)

        assert message.rendered_content is not None
        fragment = lxml.html.fragment_fromstring(message.rendered_content, create_parent=True)
        relative_to_full_url(fragment, user.realm.uri)
        fix_emojis(fragment, user.emojiset)
        fix_spoilers_in_html(fragment, user.default_language)
        change_katex_to_raw_latex(fragment)

        html = lxml.html.tostring(fragment, encoding="unicode")
        if sender:
            plain, html = prepend_sender_to_message(plain, html, sender)
        return {"plain": plain, "html": html}

    def build_sender_payload(message: Message) -> Dict[str, Any]:
        sender = sender_string(message)
        return {"sender": sender, "content": [build_message_payload(message, sender)]}

    def message_header(message: Message) -> Dict[str, Any]:
        if message.recipient.type == Recipient.PERSONAL:
            grouping: Dict[str, Any] = {"user": message.sender_id}
            narrow_link = personal_narrow_url(
                realm=user.realm,
                sender=message.sender,
            )
            header = f"You and {message.sender.full_name}"
            header_html = f"<a style='color: #ffffff;' href='{narrow_link}'>{header}</a>"
        elif message.recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
            grouping = {"huddle": message.recipient_id}
            display_recipient = get_display_recipient(message.recipient)
            narrow_link = huddle_narrow_url(
                user=user,
                display_recipient=display_recipient,
            )
            other_recipients = [r["full_name"] for r in display_recipient if r["id"] != user.id]
            header = "You and {}".format(", ".join(other_recipients))
            header_html = f"<a style='color: #ffffff;' href='{narrow_link}'>{header}</a>"
        else:
            assert message.recipient.type == Recipient.STREAM
            grouping = {"stream": message.recipient_id, "topic": message.topic_name().lower()}
            stream_id = message.recipient.type_id
            if stream_id_map is not None and stream_id in stream_id_map:
                stream = stream_id_map[stream_id]
            else:
                # Some of our callers don't populate stream_map, so
                # we just populate the stream from the database.
                stream = Stream.objects.only("id", "name").get(id=stream_id)
            narrow_link = topic_narrow_url(
                realm=user.realm,
                stream=stream,
                topic_name=message.topic_name(),
            )
            header = f"{stream.name} > {message.topic_name()}"
            stream_link = stream_narrow_url(user.realm, stream)
            header_html = f"<a href='{stream_link}'>{stream.name}</a> > <a href='{narrow_link}'>{message.topic_name()}</a>"
        return {
            "grouping": grouping,
            "plain": header,
            "html": header_html,
            "stream_message": message.recipient.type_name() == "stream",
        }

    # # Collapse message list to
    # [
    #    {
    #       "header": {
    #                   "plain":"header",
    #                   "html":"htmlheader"
    #                 }
    #       "senders":[
    #          {
    #             "sender":"sender_name",
    #             "content":[
    #                {
    #                   "plain":"content",
    #                   "html":"htmlcontent"
    #                }
    #                {
    #                   "plain":"content",
    #                   "html":"htmlcontent"
    #                }
    #             ]
    #          }
    #       ]
    #    },
    # ]

    messages.sort(key=lambda message: message.date_sent)

    for message in messages:
        header = message_header(message)

        # If we want to collapse into the previous recipient block
        if (
            len(messages_to_render) > 0
            and messages_to_render[-1]["header"]["grouping"] == header["grouping"]
        ):
            sender = sender_string(message)
            sender_block = messages_to_render[-1]["senders"]

            # Same message sender, collapse again
            if sender_block[-1]["sender"] == sender:
                sender_block[-1]["content"].append(build_message_payload(message))
            else:
                # Start a new sender block
                sender_block.append(build_sender_payload(message))
        else:
            # New recipient and sender block
            recipient_block = {"header": header, "senders": [build_sender_payload(message)]}

            messages_to_render.append(recipient_block)

    return messages_to_render


def message_content_allowed_in_missedmessage_emails(user_profile: UserProfile) -> bool:
    return (
        user_profile.realm.message_content_allowed_in_email_notifications
        and user_profile.message_content_in_email_notifications
    )


def include_realm_name_in_missedmessage_emails_subject(user_profile: UserProfile) -> bool:
    # Determines whether to include the realm name in the subject line
    # of missedmessage email notifications, based on the user's
    # realm_name_in_email_notifications_policy settings and whether the
    # user's delivery_email is associated with other active realms.
    if (
        user_profile.realm_name_in_email_notifications_policy
        == UserProfile.REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_AUTOMATIC
    ):
        realms_count = UserProfile.objects.filter(
            delivery_email=user_profile.delivery_email,
            is_active=True,
            is_bot=False,
            realm__deactivated=False,
        ).count()
        return realms_count > 1
    return (
        user_profile.realm_name_in_email_notifications_policy
        == UserProfile.REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_ALWAYS
    )


def do_send_missedmessage_events_reply_in_zulip(
    user_profile: UserProfile, missed_messages: List[Dict[str, Any]], message_count: int
) -> None:
    """
    Send a reminder email to a user if she's missed some direct messages
    by being offline.

    The email will have its reply to address set to a limited used email
    address that will send a Zulip message to the correct recipient. This
    allows the user to respond to missed direct messages, huddles, and
    @-mentions directly from the email.

    `user_profile` is the user to send the reminder to
    `missed_messages` is a list of dictionaries to Message objects and other data
                      for a group of messages that share a recipient (and topic)
    """
    from zerver.context_processors import common_context

    recipients = {
        (msg["message"].recipient_id, msg["message"].topic_name().lower())
        for msg in missed_messages
    }
    assert len(recipients) == 1, f"Unexpectedly multiple recipients: {recipients!r}"

    # This link is no longer a part of the email, but keeping the code in case
    # we find a clean way to add it back in the future
    unsubscribe_link = one_click_unsubscribe_link(user_profile, "missed_messages")
    context = common_context(user_profile)
    context.update(
        name=user_profile.full_name,
        message_count=message_count,
        unsubscribe_link=unsubscribe_link,
        include_realm_name_in_missedmessage_emails_subject=include_realm_name_in_missedmessage_emails_subject(
            user_profile
        ),
    )

    mentioned_user_group_name = None
    mentioned_user_group_members_count = None
    mentioned_user_group = get_mentioned_user_group(missed_messages, user_profile)
    if mentioned_user_group is not None:
        mentioned_user_group_name = mentioned_user_group.name
        mentioned_user_group_members_count = mentioned_user_group.members_count

    triggers = [message["trigger"] for message in missed_messages]
    unique_triggers = set(triggers)

    personal_mentioned = any(
        message["trigger"] == NotificationTriggers.MENTION
        and message["mentioned_user_group_id"] is None
        for message in missed_messages
    )

    mention = (
        NotificationTriggers.MENTION in unique_triggers
        or NotificationTriggers.TOPIC_WILDCARD_MENTION in unique_triggers
        or NotificationTriggers.STREAM_WILDCARD_MENTION in unique_triggers
        or NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC in unique_triggers
        or NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC in unique_triggers
    )

    context.update(
        mention=mention,
        personal_mentioned=personal_mentioned,
        topic_wildcard_mentioned=NotificationTriggers.TOPIC_WILDCARD_MENTION in unique_triggers,
        stream_wildcard_mentioned=NotificationTriggers.STREAM_WILDCARD_MENTION in unique_triggers,
        stream_email_notify=NotificationTriggers.STREAM_EMAIL in unique_triggers,
        followed_topic_email_notify=NotificationTriggers.FOLLOWED_TOPIC_EMAIL in unique_triggers,
        topic_wildcard_mentioned_in_followed_topic=NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
        in unique_triggers,
        stream_wildcard_mentioned_in_followed_topic=NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
        in unique_triggers,
        mentioned_user_group_name=mentioned_user_group_name,
    )

    # If this setting (email mirroring integration) is enabled, only then
    # can users reply to email to send message to Zulip. Thus, one must
    # ensure to display warning in the template.
    if settings.EMAIL_GATEWAY_PATTERN:
        context.update(
            reply_to_zulip=True,
        )
    else:
        context.update(
            reply_to_zulip=False,
        )

    from zerver.lib.email_mirror import create_missed_message_address

    reply_to_address = create_missed_message_address(user_profile, missed_messages[0]["message"])
    if reply_to_address == FromAddress.NOREPLY:
        reply_to_name = ""
    else:
        reply_to_name = "Zulip"

    senders = list({m["message"].sender for m in missed_messages})
    if missed_messages[0]["message"].recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        display_recipient = get_display_recipient(missed_messages[0]["message"].recipient)
        narrow_url = huddle_narrow_url(
            user=user_profile,
            display_recipient=display_recipient,
        )
        context.update(narrow_url=narrow_url)
        other_recipients = [r["full_name"] for r in display_recipient if r["id"] != user_profile.id]
        context.update(group_pm=True)
        if len(other_recipients) == 2:
            huddle_display_name = " and ".join(other_recipients)
            context.update(huddle_display_name=huddle_display_name)
        elif len(other_recipients) == 3:
            huddle_display_name = (
                f"{other_recipients[0]}, {other_recipients[1]}, and {other_recipients[2]}"
            )
            context.update(huddle_display_name=huddle_display_name)
        else:
            huddle_display_name = "{}, and {} others".format(
                ", ".join(other_recipients[:2]), len(other_recipients) - 2
            )
            context.update(huddle_display_name=huddle_display_name)
    elif missed_messages[0]["message"].recipient.type == Recipient.PERSONAL:
        narrow_url = personal_narrow_url(
            realm=user_profile.realm,
            sender=missed_messages[0]["message"].sender,
        )
        context.update(narrow_url=narrow_url)
        context.update(private_message=True)
    elif (
        context["mention"]
        or context["stream_email_notify"]
        or context["followed_topic_email_notify"]
    ):
        # Keep only the senders who actually mentioned the user
        if context["mention"]:
            senders = list(
                {
                    m["message"].sender
                    for m in missed_messages
                    if m["trigger"]
                    in [
                        NotificationTriggers.MENTION,
                        NotificationTriggers.TOPIC_WILDCARD_MENTION,
                        NotificationTriggers.STREAM_WILDCARD_MENTION,
                        NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
                        NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
                    ]
                }
            )
        message = missed_messages[0]["message"]
        assert message.recipient.type == Recipient.STREAM
        stream = Stream.objects.only("id", "name").get(id=message.recipient.type_id)
        narrow_url = topic_narrow_url(
            realm=user_profile.realm,
            stream=stream,
            topic_name=message.topic_name(),
        )
        context.update(narrow_url=narrow_url)
        topic_resolved, topic_name = get_topic_resolution_and_bare_name(message.topic_name())
        context.update(
            channel_name=stream.name,
            topic_name=topic_name,
            topic_resolved=topic_resolved,
        )
    else:
        raise AssertionError("Invalid messages!")

    # If message content is disabled, then flush all information we pass to email.
    if not message_content_allowed_in_missedmessage_emails(user_profile):
        realm = user_profile.realm
        context.update(
            reply_to_zulip=False,
            messages=[],
            sender_str="",
            realm_str=realm.name,
            huddle_display_name="",
            show_message_content=False,
            message_content_disabled_by_user=not user_profile.message_content_in_email_notifications,
            message_content_disabled_by_realm=not realm.message_content_allowed_in_email_notifications,
        )
    else:
        context.update(
            messages=build_message_list(
                user=user_profile,
                messages=[m["message"] for m in missed_messages],
            ),
            sender_str=", ".join(sender.full_name for sender in senders),
            realm_str=user_profile.realm.name,
            show_message_content=True,
        )

    # Soft reactivate the long_term_idle user personally mentioned
    soft_reactivate_if_personal_notification(
        user_profile, unique_triggers, mentioned_user_group_members_count
    )

    with override_language(user_profile.default_language):
        from_name: str = _("{service_name} notifications").format(
            service_name=settings.INSTALLATION_NAME
        )
    from_address = FromAddress.NOREPLY

    email_dict = {
        "template_prefix": "zerver/emails/missed_message",
        "to_user_ids": [user_profile.id],
        "from_name": from_name,
        "from_address": from_address,
        "reply_to_email": str(Address(display_name=reply_to_name, addr_spec=reply_to_address)),
        "context": context,
    }
    queue_json_publish("email_senders", email_dict)

    user_profile.last_reminder = timezone_now()
    user_profile.save(update_fields=["last_reminder"])


@dataclass
class MissedMessageData:
    trigger: str
    mentioned_user_group_id: Optional[int] = None


def handle_missedmessage_emails(
    user_profile_id: int, message_ids: Dict[int, MissedMessageData]
) -> None:
    user_profile = get_user_profile_by_id(user_profile_id)
    if user_profile.is_bot:  # nocoverage
        # We don't expect to reach here for bot users. However, this code exists
        # to find and throw away any pre-existing events in the queue while
        # upgrading from versions before our notifiability logic was implemented.
        # TODO/compatibility: This block can be removed when one can no longer
        # upgrade from versions <= 4.0 to versions >= 5.0
        logger.warning("Send-email event found for bot user %s. Skipping.", user_profile_id)
        return

    if not user_profile.enable_offline_email_notifications:
        # BUG: Investigate why it's possible to get here.
        return  # nocoverage

    # Note: This query structure automatically filters out any
    # messages that were permanently deleted, since those would now be
    # in the ArchivedMessage table, not the Message table.
    messages = Message.objects.filter(
        # Uses index: zerver_message_pkey
        usermessage__user_profile_id=user_profile,
        id__in=message_ids,
        usermessage__flags=~UserMessage.flags.read,
        # Cancel missed-message emails for deleted messages
    ).exclude(content="(deleted)")

    if not messages:
        return

    # We bucket messages by tuples that identify similar messages.
    # For streams it's recipient_id and topic.
    # For direct messages it's recipient id and sender.
    messages_by_bucket: Dict[Tuple[int, Union[int, str]], List[Message]] = defaultdict(list)
    for msg in messages:
        if msg.recipient.type == Recipient.PERSONAL:
            # For direct messages group using (recipient, sender).
            messages_by_bucket[(msg.recipient_id, msg.sender_id)].append(msg)
        else:
            messages_by_bucket[(msg.recipient_id, msg.topic_name().lower())].append(msg)

    message_count_by_bucket = {
        bucket_tup: len(msgs) for bucket_tup, msgs in messages_by_bucket.items()
    }

    for msg_list in messages_by_bucket.values():
        msg = min(msg_list, key=lambda msg: msg.date_sent)
        if msg.is_stream_message() and UserMessage.has_any_mentions(user_profile_id, msg.id):
            context_messages = get_context_for_message(msg)
            filtered_context_messages = bulk_access_messages(user_profile, context_messages)
            msg_list.extend(filtered_context_messages)

    # Sort emails by least recently-active discussion.
    bucket_tups: List[Tuple[Tuple[int, Union[int, str]], int]] = []
    for bucket_tup, msg_list in messages_by_bucket.items():
        max_message_id = max(msg_list, key=lambda msg: msg.id).id
        bucket_tups.append((bucket_tup, max_message_id))

    bucket_tups = sorted(bucket_tups, key=lambda x: x[1])

    # Send an email per bucket.
    for bucket_tup, ignored_max_id in bucket_tups:
        unique_messages = {}
        for m in messages_by_bucket[bucket_tup]:
            message_info = message_ids.get(m.id)
            unique_messages[m.id] = dict(
                message=m,
                trigger=message_info.trigger if message_info else None,
                mentioned_user_group_id=(
                    message_info.mentioned_user_group_id if message_info is not None else None
                ),
            )
        do_send_missedmessage_events_reply_in_zulip(
            user_profile,
            list(unique_messages.values()),
            message_count_by_bucket[bucket_tup],
        )


def get_onboarding_email_schedule(user: UserProfile) -> Dict[str, timedelta]:
    onboarding_emails = {
        # The delay should be 1 hour before the below specified number of days
        # as our goal is to maximize the chance that this email is near the top
        # of the user's inbox when the user sits down to deal with their inbox,
        # or comes in while they are dealing with their inbox.
        "onboarding_zulip_topics": timedelta(days=2, hours=-1),
        "onboarding_zulip_guide": timedelta(days=4, hours=-1),
        "onboarding_team_to_zulip": timedelta(days=6, hours=-1),
    }

    user_tz = user.timezone
    if user_tz == "":
        user_tz = "UTC"
    signup_day = user.date_joined.astimezone(
        zoneinfo.ZoneInfo(canonicalize_timezone(user_tz))
    ).isoweekday()

    # General rules for scheduling welcome emails flow:
    # -Do not send emails on Saturday or Sunday
    # -Have at least one weekday between each (potential) email

    # User signed up on Monday
    if signup_day == 1:
        # Send onboarding_team_to_zulip on Tuesday
        onboarding_emails["onboarding_team_to_zulip"] = timedelta(days=8, hours=-1)

    # User signed up on Tuesday
    if signup_day == 2:
        # Send onboarding_zulip_guide on Monday
        onboarding_emails["onboarding_zulip_guide"] = timedelta(days=6, hours=-1)
        # Send onboarding_team_to_zulip on Wednesday
        onboarding_emails["onboarding_team_to_zulip"] = timedelta(days=8, hours=-1)

    # User signed up on Wednesday
    if signup_day == 3:
        # Send onboarding_zulip_guide on Tuesday
        onboarding_emails["onboarding_zulip_guide"] = timedelta(days=6, hours=-1)
        # Send onboarding_team_to_zulip on Thursday
        onboarding_emails["onboarding_team_to_zulip"] = timedelta(days=8, hours=-1)

    # User signed up on Thursday
    if signup_day == 4:
        # Send onboarding_zulip_topics on Monday
        onboarding_emails["onboarding_zulip_topics"] = timedelta(days=4, hours=-1)
        # Send onboarding_zulip_guide on Wednesday
        onboarding_emails["onboarding_zulip_guide"] = timedelta(days=6, hours=-1)
        # Send onboarding_team_to_zulip on Friday
        onboarding_emails["onboarding_team_to_zulip"] = timedelta(days=8, hours=-1)

    # User signed up on Friday
    if signup_day == 5:
        # Send onboarding_zulip_topics on Tuesday
        onboarding_emails["onboarding_zulip_topics"] = timedelta(days=4, hours=-1)
        # Send onboarding_zulip_guide on Thursday
        onboarding_emails["onboarding_zulip_guide"] = timedelta(days=6, hours=-1)
        # Send onboarding_team_to_zulip on Monday
        onboarding_emails["onboarding_team_to_zulip"] = timedelta(days=10, hours=-1)

    # User signed up on Saturday; no adjustments needed

    # User signed up on Sunday
    if signup_day == 7:
        # Send onboarding_team_to_zulip on Monday
        onboarding_emails["onboarding_team_to_zulip"] = timedelta(days=8, hours=-1)

    return onboarding_emails


def get_org_type_zulip_guide(realm: Realm) -> Tuple[Any, str]:
    for realm_type, realm_type_details in Realm.ORG_TYPES.items():
        if realm_type_details["id"] == realm.org_type:
            organization_type_in_template = realm_type

            # There are two education organization types that receive the same email
            # content, so we simplify to one shared template context value here.
            if organization_type_in_template == "education_nonprofit":
                organization_type_in_template = "education"

            return (realm_type_details["onboarding_zulip_guide_url"], organization_type_in_template)

    # Log problem, and return values that will not send onboarding_zulip_guide email.
    logging.error("Unknown organization type '%s'", realm.org_type)
    return (None, "")


def welcome_sender_information() -> Tuple[Optional[str], str]:
    if settings.WELCOME_EMAIL_SENDER is not None:
        from_name = settings.WELCOME_EMAIL_SENDER["name"]
        from_address = settings.WELCOME_EMAIL_SENDER["email"]
    else:
        from_name = None
        from_address = FromAddress.support_placeholder

    return (from_name, from_address)


def send_account_registered_email(user: UserProfile, realm_creation: bool = False) -> None:
    # Imported here to avoid import cycles.
    from zerver.context_processors import common_context

    if user.delivery_email == "":
        # Do not attempt to enqueue welcome emails for users without an email address.
        # The assertions here are to help document the only circumstance under which
        # this condition should be possible.
        assert user.realm.demo_organization_scheduled_deletion_date is not None and realm_creation
        return

    from_name, from_address = welcome_sender_information()
    realm_url = user.realm.uri

    account_registered_context = common_context(user)
    account_registered_context.update(
        realm_creation=realm_creation,
        email=user.delivery_email,
        is_realm_admin=user.is_realm_admin,
        is_demo_organization=user.realm.demo_organization_scheduled_deletion_date is not None,
    )

    account_registered_context["getting_organization_started_link"] = (
        realm_url + "/help/getting-your-organization-started-with-zulip"
    )

    account_registered_context["getting_user_started_link"] = (
        realm_url + "/help/getting-started-with-zulip"
    )

    # Imported here to avoid import cycles.
    from zproject.backends import ZulipLDAPAuthBackend, email_belongs_to_ldap

    if email_belongs_to_ldap(user.realm, user.delivery_email):
        account_registered_context["ldap"] = True
        for backend in get_backends():
            # If the user is doing authentication via LDAP, Note that
            # we exclude ZulipLDAPUserPopulator here, since that
            # isn't used for authentication.
            if isinstance(backend, ZulipLDAPAuthBackend):
                account_registered_context["ldap_username"] = backend.django_to_ldap_username(
                    user.delivery_email
                )
                break

    send_future_email(
        "zerver/emails/account_registered",
        user.realm,
        to_user_ids=[user.id],
        from_name=from_name,
        from_address=from_address,
        context=account_registered_context,
    )


def enqueue_welcome_emails(user: UserProfile, realm_creation: bool = False) -> None:
    # Imported here to avoid import cycles.
    from zerver.context_processors import common_context

    if user.delivery_email == "":
        # Do not attempt to enqueue welcome emails for users without an email address.
        # The assertions here are to help document the only circumstance under which
        # this condition should be possible.
        assert user.realm.demo_organization_scheduled_deletion_date is not None and realm_creation
        return

    from_name, from_address = welcome_sender_information()
    other_account_count = (
        UserProfile.objects.filter(delivery_email__iexact=user.delivery_email)
        .exclude(id=user.id)
        .count()
    )
    unsubscribe_link = one_click_unsubscribe_link(user, "welcome")
    realm_url = user.realm.uri

    # Any emails scheduled below should be added to the logic in get_onboarding_email_schedule
    # to determine how long to delay sending the email based on when the user signed up.
    onboarding_email_schedule = get_onboarding_email_schedule(user)

    if other_account_count == 0:
        onboarding_zulip_topics_context = common_context(user)

        onboarding_zulip_topics_context.update(
            unsubscribe_link=unsubscribe_link,
            move_messages_link=realm_url + "/help/move-content-to-another-topic",
            rename_topics_link=realm_url + "/help/rename-a-topic",
            move_channels_link=realm_url + "/help/move-content-to-another-channel",
        )

        send_future_email(
            "zerver/emails/onboarding_zulip_topics",
            user.realm,
            to_user_ids=[user.id],
            from_name=from_name,
            from_address=from_address,
            context=onboarding_zulip_topics_context,
            delay=onboarding_email_schedule["onboarding_zulip_topics"],
        )

    # We only send the onboarding_zulip_guide email for a subset of Realm.ORG_TYPES
    onboarding_zulip_guide_url, organization_type_reference = get_org_type_zulip_guide(user.realm)

    # Only send follow_zulip_guide to "/for/communities/" guide if user is realm admin.
    # TODO: Remove this condition and related tests when guide is updated;
    # see https://github.com/zulip/zulip/issues/24822.
    if (
        onboarding_zulip_guide_url == Realm.ORG_TYPES["community"]["onboarding_zulip_guide_url"]
        and not user.is_realm_admin
    ):
        onboarding_zulip_guide_url = None

    if onboarding_zulip_guide_url is not None:
        onboarding_zulip_guide_context = common_context(user)
        onboarding_zulip_guide_context.update(
            # We use the same unsubscribe link in both onboarding_zulip_topics
            # and onboarding_zulip_guide as these links do not expire.
            unsubscribe_link=unsubscribe_link,
            organization_type=organization_type_reference,
            zulip_guide_link=onboarding_zulip_guide_url,
        )

        send_future_email(
            "zerver/emails/onboarding_zulip_guide",
            user.realm,
            to_user_ids=[user.id],
            from_name=from_name,
            from_address=from_address,
            context=onboarding_zulip_guide_context,
            delay=onboarding_email_schedule["onboarding_zulip_guide"],
        )

    # We only send the onboarding_team_to_zulip email to user who created the organization.
    if realm_creation:
        onboarding_team_to_zulip_context = common_context(user)
        onboarding_team_to_zulip_context.update(
            unsubscribe_link=unsubscribe_link,
            get_organization_started=realm_url
            + "/help/getting-your-organization-started-with-zulip",
            invite_users=realm_url + "/help/invite-users-to-join",
            trying_out_zulip=realm_url + "/help/trying-out-zulip",
            why_zulip="https://zulip.com/why-zulip/",
        )

        send_future_email(
            "zerver/emails/onboarding_team_to_zulip",
            user.realm,
            to_user_ids=[user.id],
            from_name=from_name,
            from_address=from_address,
            context=onboarding_team_to_zulip_context,
            delay=onboarding_email_schedule["onboarding_team_to_zulip"],
        )


def convert_html_to_markdown(html: str) -> str:
    # html2text is GPL licensed, so run it as a subprocess.
    markdown = subprocess.check_output(
        [os.path.join(sys.prefix, "bin", "html2text")], input=html, text=True
    ).strip()

    # We want images to get linked and inline previewed, but html2text will turn
    # them into links of the form `![](http://foo.com/image.png)`, which is
    # ugly. Run a regex over the resulting description, turning links of the
    # form `![](http://foo.com/image.png?12345)` into
    # `[image.png](http://foo.com/image.png)`.
    return re.sub(r"!\[\]\((\S*)/(\S*)\?(\S*)\)", "[\\2](\\1/\\2)", markdown)


from typing import cast, Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Text

from confirmation.models import Confirmation, create_confirmation_link
from django.conf import settings
from django.template import loader
from django.utils.timezone import now as timezone_now
from zerver.decorator import statsd_increment
from zerver.lib.send_email import send_future_email, FromAddress
from zerver.lib.queue import queue_json_publish
from zerver.models import (
    Recipient,
    ScheduledEmail,
    UserMessage,
    Stream,
    get_display_recipient,
    UserProfile,
    get_user,
    get_user_profile_by_id,
    receives_offline_email_notifications,
    get_context_for_message,
    Message,
    Realm,
)

from datetime import timedelta, datetime
from email.utils import formataddr
import lxml.html
import re
import subprocess
import ujson
import urllib
from collections import defaultdict
import pytz

def one_click_unsubscribe_link(user_profile: UserProfile, email_type: str) -> str:
    """
    Generate a unique link that a logged-out user can visit to unsubscribe from
    Zulip e-mails without having to first log in.
    """
    return create_confirmation_link(user_profile, user_profile.realm.host,
                                    Confirmation.UNSUBSCRIBE,
                                    url_args = {'email_type': email_type})

def hash_util_encode(string: Text) -> Text:
    # Do the same encoding operation as hash_util.encodeHashComponent on the
    # frontend.
    # `safe` has a default value of "/", but we want those encoded, too.
    return urllib.parse.quote(
        string.encode("utf-8"), safe=b"").replace(".", "%2E").replace("%", ".")

def encode_stream(stream_id: int, stream_name: Text) -> Text:
    # We encode streams for urls as something like 99-Verona.
    stream_name = stream_name.replace(' ', '-')
    return str(stream_id) + '-' + hash_util_encode(stream_name)

def pm_narrow_url(realm: Realm, participants: List[Text]) -> Text:
    participants.sort()
    base_url = "%s/#narrow/pm-with/" % (realm.uri,)
    return base_url + hash_util_encode(",".join(participants))

def stream_narrow_url(realm: Realm, stream: Stream) -> Text:
    base_url = "%s/#narrow/stream/" % (realm.uri,)
    return base_url + encode_stream(stream.id, stream.name)

def topic_narrow_url(realm: Realm, stream: Stream, topic: Text) -> Text:
    base_url = "%s/#narrow/stream/" % (realm.uri,)
    return "%s%s/topic/%s" % (base_url,
                              encode_stream(stream.id, stream.name),
                              hash_util_encode(topic))

def relative_to_full_url(base_url: Text, content: Text) -> Text:
    # Convert relative URLs to absolute URLs.
    fragment = lxml.html.fromstring(content)

    # We handle narrow URLs separately because of two reasons:
    # 1: 'lxml' seems to be having an issue in dealing with URLs that begin
    # `#` due to which it doesn't add a `/` before joining the base_url to
    # the relative URL.
    # 2: We also need to update the title attribute in the narrow links which
    # is not possible with `make_links_absolute()`.
    for link_info in fragment.iterlinks():
        elem, attrib, link, pos = link_info
        match = re.match("/?#narrow/", link)
        if match is not None:
            link = re.sub(r"^/?#narrow/", base_url + "/#narrow/", link)
            elem.set(attrib, link)
            # Only manually linked narrow URLs have title attribute set.
            if elem.get('title') is not None:
                elem.set('title', link)

    # Inline images can't be displayed in the emails as the request
    # from the mail server can't be authenticated because it has no
    # user_profile object linked to it. So we scrub the inline image
    # container.
    inline_image_containers = fragment.find_class("message_inline_image")
    for container in inline_image_containers:
        container.drop_tree()

    # The previous block handles most inline images, but for messages
    # where the entire markdown input was just the URL of an image
    # (i.e. the entire body is a message_inline_image object), the
    # entire message body will be that image element; here, we need a
    # more drastic edit to the content.
    if fragment.get('class') == 'message_inline_image':
        content_template = '<p><a href="%s" target="_blank" title="%s">%s</a></p>'
        image_link = fragment.find('a').get('href')
        image_title = fragment.find('a').get('title')
        new_content = (content_template % (image_link, image_title, image_link))
        fragment = lxml.html.fromstring(new_content)

    fragment.make_links_absolute(base_url)
    content = lxml.html.tostring(fragment).decode("utf-8")

    return content

def fix_emojis(content: Text, base_url: Text, emojiset: Text) -> Text:
    def make_emoji_img_elem(emoji_span_elem: Any) -> Dict[str, Any]:
        # Convert the emoji spans to img tags.
        classes = emoji_span_elem.get('class')
        match = re.search('emoji-(?P<emoji_code>\S+)', classes)
        emoji_code = match.group('emoji_code')
        emoji_name = emoji_span_elem.get('title')
        alt_code = emoji_span_elem.text
        image_url = base_url + '/static/generated/emoji/images-%(emojiset)s-64/%(emoji_code)s.png' % {
            'emojiset': emojiset,
            'emoji_code': emoji_code
        }
        img_elem = lxml.html.fromstring(
            '<img alt="%(alt_code)s" src="%(image_url)s" title="%(title)s">' % {
                'alt_code': alt_code,
                'image_url': image_url,
                'title': emoji_name,
            })
        img_elem.set('style', 'height: 20px;')
        img_elem.tail = emoji_span_elem.tail
        return img_elem

    fragment = lxml.html.fromstring(content)
    for elem in fragment.cssselect('span.emoji'):
        parent = elem.getparent()
        img_elem = make_emoji_img_elem(elem)
        parent.replace(elem, img_elem)

    for realm_emoji in fragment.cssselect('.emoji'):
        del realm_emoji.attrib['class']
        realm_emoji.set('style', 'height: 20px;')

    content = lxml.html.tostring(fragment).decode('utf-8')
    return content

def build_message_list(user_profile: UserProfile, messages: List[Message]) -> List[Dict[str, Any]]:
    """
    Builds the message list object for the missed message email template.
    The messages are collapsed into per-recipient and per-sender blocks, like
    our web interface
    """
    messages_to_render = []  # type: List[Dict[str, Any]]

    def sender_string(message: Message) -> Text:
        if message.recipient.type in (Recipient.STREAM, Recipient.HUDDLE):
            return message.sender.full_name
        else:
            return ''

    def fix_plaintext_image_urls(content: Text) -> Text:
        # Replace image URLs in plaintext content of the form
        #     [image name](image url)
        # with a simple hyperlink.
        return re.sub(r"\[(\S*)\]\((\S*)\)", r"\2", content)

    def build_message_payload(message: Message) -> Dict[str, Text]:
        plain = message.content
        plain = fix_plaintext_image_urls(plain)
        # There's a small chance of colliding with non-Zulip URLs containing
        # "/user_uploads/", but we don't have much information about the
        # structure of the URL to leverage. We can't use `relative_to_full_url()`
        # function here because it uses a stricter regex which will not work for
        # plain text.
        plain = re.sub(
            r"/user_uploads/(\S*)",
            user_profile.realm.uri + r"/user_uploads/\1", plain)

        assert message.rendered_content is not None
        html = message.rendered_content
        html = relative_to_full_url(user_profile.realm.uri, html)
        html = fix_emojis(html, user_profile.realm.uri, user_profile.emojiset)

        return {'plain': plain, 'html': html}

    def build_sender_payload(message: Message) -> Dict[str, Any]:
        sender = sender_string(message)
        return {'sender': sender,
                'content': [build_message_payload(message)]}

    def message_header(user_profile: UserProfile, message: Message) -> Dict[str, Any]:
        if message.recipient.type == Recipient.PERSONAL:
            header = "You and %s" % (message.sender.full_name,)
            html_link = pm_narrow_url(user_profile.realm, [message.sender.email])
            header_html = "<a style='color: #ffffff;' href='%s'>%s</a>" % (html_link, header)
        elif message.recipient.type == Recipient.HUDDLE:
            disp_recipient = get_display_recipient(message.recipient)
            assert not isinstance(disp_recipient, Text)
            other_recipients = [r['full_name'] for r in disp_recipient
                                if r['email'] != user_profile.email]
            header = "You and %s" % (", ".join(other_recipients),)
            html_link = pm_narrow_url(user_profile.realm, [r["email"] for r in disp_recipient
                                      if r["email"] != user_profile.email])
            header_html = "<a style='color: #ffffff;' href='%s'>%s</a>" % (html_link, header)
        else:
            stream = Stream.objects.only('id', 'name').get(id=message.recipient.type_id)
            header = "%s > %s" % (stream.name, message.topic_name())
            stream_link = stream_narrow_url(user_profile.realm, stream)
            topic_link = topic_narrow_url(user_profile.realm, stream, message.subject)
            header_html = "<a href='%s'>%s</a> > <a href='%s'>%s</a>" % (
                stream_link, stream.name, topic_link, message.subject)
        return {"plain": header,
                "html": header_html,
                "stream_message": message.recipient.type_name() == "stream"}

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

    messages.sort(key=lambda message: message.pub_date)

    for message in messages:
        header = message_header(user_profile, message)

        # If we want to collapse into the previous recipient block
        if len(messages_to_render) > 0 and messages_to_render[-1]['header'] == header:
            sender = sender_string(message)
            sender_block = messages_to_render[-1]['senders']

            # Same message sender, collapse again
            if sender_block[-1]['sender'] == sender:
                sender_block[-1]['content'].append(build_message_payload(message))
            else:
                # Start a new sender block
                sender_block.append(build_sender_payload(message))
        else:
            # New recipient and sender block
            recipient_block = {'header': header,
                               'senders': [build_sender_payload(message)]}

            messages_to_render.append(recipient_block)

    return messages_to_render

@statsd_increment("missed_message_reminders")
def do_send_missedmessage_events_reply_in_zulip(user_profile: UserProfile,
                                                missed_messages: List[Message],
                                                message_count: int) -> None:
    """
    Send a reminder email to a user if she's missed some PMs by being offline.

    The email will have its reply to address set to a limited used email
    address that will send a zulip message to the correct recipient. This
    allows the user to respond to missed PMs, huddles, and @-mentions directly
    from the email.

    `user_profile` is the user to send the reminder to
    `missed_messages` is a list of Message objects to remind about they should
                      all have the same recipient and subject
    """
    from zerver.context_processors import common_context
    # Disabled missedmessage emails internally
    if not user_profile.enable_offline_email_notifications:
        return

    recipients = set((msg.recipient_id, msg.subject) for msg in missed_messages)
    if len(recipients) != 1:
        raise ValueError(
            'All missed_messages must have the same recipient and subject %r' %
            recipients
        )

    unsubscribe_link = one_click_unsubscribe_link(user_profile, "missed_messages")
    context = common_context(user_profile)
    context.update({
        'name': user_profile.full_name,
        'message_count': message_count,
        'mention': missed_messages[0].is_stream_message(),
        'unsubscribe_link': unsubscribe_link,
        'realm_name_in_notifications': user_profile.realm_name_in_notifications,
        'show_message_content': user_profile.message_content_in_email_notifications,
    })

    # If this setting (email mirroring integration) is enabled, only then
    # can users reply to email to send message to Zulip. Thus, one must
    # ensure to display warning in the template.
    if settings.EMAIL_GATEWAY_PATTERN:
        context.update({
            'reply_warning': False,
            'reply_to_zulip': True,
        })
    else:
        context.update({
            'reply_warning': True,
            'reply_to_zulip': False,
        })

    from zerver.lib.email_mirror import create_missed_message_address
    reply_to_address = create_missed_message_address(user_profile, missed_messages[0])
    if reply_to_address == FromAddress.NOREPLY:
        reply_to_name = None
    else:
        reply_to_name = "Zulip"

    senders = list(set(m.sender for m in missed_messages))
    if (missed_messages[0].recipient.type == Recipient.HUDDLE):
        display_recipient = get_display_recipient(missed_messages[0].recipient)
        # Make sure that this is a list of strings, not a string.
        assert not isinstance(display_recipient, Text)
        other_recipients = [r['full_name'] for r in display_recipient
                            if r['id'] != user_profile.id]
        context.update({'group_pm': True})
        if len(other_recipients) == 2:
            huddle_display_name = "%s" % (" and ".join(other_recipients))
            context.update({'huddle_display_name': huddle_display_name})
        elif len(other_recipients) == 3:
            huddle_display_name = "%s, %s, and %s" % (
                other_recipients[0], other_recipients[1], other_recipients[2])
            context.update({'huddle_display_name': huddle_display_name})
        else:
            huddle_display_name = "%s, and %s others" % (
                ', '.join(other_recipients[:2]), len(other_recipients) - 2)
            context.update({'huddle_display_name': huddle_display_name})
    elif (missed_messages[0].recipient.type == Recipient.PERSONAL):
        context.update({'private_message': True})
    else:
        # Keep only the senders who actually mentioned the user
        #
        # TODO: When we add wildcard mentions that send emails, add
        # them to the filter here.
        senders = list(set(m.sender for m in missed_messages if
                           UserMessage.objects.filter(message=m, user_profile=user_profile,
                                                      flags=UserMessage.flags.mentioned).exists()))
        context.update({'at_mention': True})

    # If message content is disabled, then flush all information we pass to email.
    if not user_profile.message_content_in_email_notifications:
        context.update({
            'reply_to_zulip': False,
            'messages': [],
            'sender_str': "",
            'realm_str': user_profile.realm.name,
            'huddle_display_name': "",
        })
    else:
        context.update({
            'messages': build_message_list(user_profile, missed_messages),
            'sender_str': ", ".join(sender.full_name for sender in senders),
            'realm_str': user_profile.realm.name,
        })

    from_name = "Zulip missed messages"  # type: Text
    from_address = FromAddress.NOREPLY
    if len(senders) == 1 and settings.SEND_MISSED_MESSAGE_EMAILS_AS_USER:
        # If this setting is enabled, you can reply to the Zulip
        # missed message emails directly back to the original sender.
        # However, one must ensure the Zulip server is in the SPF
        # record for the domain, or there will be spam/deliverability
        # problems.
        sender = senders[0]
        from_name, from_address = (sender.full_name, sender.email)
        context.update({
            'reply_warning': False,
            'reply_to_zulip': False,
        })

    email_dict = {
        'template_prefix': 'zerver/emails/missed_message',
        'to_user_id': user_profile.id,
        'from_name': from_name,
        'from_address': from_address,
        'reply_to_email': formataddr((reply_to_name, reply_to_address)),
        'context': context}
    queue_json_publish("email_senders", email_dict)

    user_profile.last_reminder = timezone_now()
    user_profile.save(update_fields=['last_reminder'])

def handle_missedmessage_emails(user_profile_id: int,
                                missed_email_events: Iterable[Dict[str, Any]]) -> None:
    message_ids = [event.get('message_id') for event in missed_email_events]

    user_profile = get_user_profile_by_id(user_profile_id)
    if not receives_offline_email_notifications(user_profile):
        return

    messages = Message.objects.filter(usermessage__user_profile_id=user_profile,
                                      id__in=message_ids,
                                      usermessage__flags=~UserMessage.flags.read)

    # Cancel missed-message emails for deleted messages
    messages = [um for um in messages if um.content != "(deleted)"]

    if not messages:
        return

    messages_by_recipient_subject = defaultdict(list)  # type: Dict[Tuple[int, Text], List[Message]]
    for msg in messages:
        if msg.recipient.type == Recipient.PERSONAL:
            # For PM's group using (recipient, sender).
            messages_by_recipient_subject[(msg.recipient_id, msg.sender_id)].append(msg)
        else:
            messages_by_recipient_subject[(msg.recipient_id, msg.topic_name())].append(msg)

    message_count_by_recipient_subject = {
        recipient_subject: len(msgs)
        for recipient_subject, msgs in messages_by_recipient_subject.items()
    }

    for msg_list in messages_by_recipient_subject.values():
        msg = min(msg_list, key=lambda msg: msg.pub_date)
        if msg.is_stream_message():
            msg_list.extend(get_context_for_message(msg))

    # Send an email per recipient subject pair
    for recipient_subject, msg_list in messages_by_recipient_subject.items():
        unique_messages = {m.id: m for m in msg_list}
        do_send_missedmessage_events_reply_in_zulip(
            user_profile,
            list(unique_messages.values()),
            message_count_by_recipient_subject[recipient_subject],
        )

def clear_scheduled_invitation_emails(email: str) -> None:
    """Unlike most scheduled emails, invitation emails don't have an
    existing user object to key off of, so we filter by address here."""
    items = ScheduledEmail.objects.filter(address__iexact=email,
                                          type=ScheduledEmail.INVITATION_REMINDER)
    items.delete()

def clear_scheduled_emails(user_id: int, email_type: Optional[int]=None) -> None:
    items = ScheduledEmail.objects.filter(user_id=user_id)
    if email_type is not None:
        items = items.filter(type=email_type)
    items.delete()

def log_digest_event(msg: Text) -> None:
    import logging
    logging.basicConfig(filename=settings.DIGEST_LOG_PATH, level=logging.INFO)
    logging.info(msg)

def followup_day2_email_delay(user: UserProfile) -> timedelta:
    days_to_delay = 2
    user_tz = user.timezone
    if user_tz == '':
        user_tz = 'UTC'
    signup_day = user.date_joined.astimezone(pytz.timezone(user_tz)).isoweekday()
    if signup_day == 5:
        # If the day is Friday then delay should be till Monday
        days_to_delay = 3
    elif signup_day == 4:
        # If the day is Thursday then delay should be till Friday
        days_to_delay = 1

    # The delay should be 1 hour before the above calculated delay as
    # our goal is to maximize the chance that this email is near the top
    # of the user's inbox when the user sits down to deal with their inbox,
    # or comes in while they are dealing with their inbox.
    return timedelta(days=days_to_delay, hours=-1)

def enqueue_welcome_emails(user: UserProfile) -> None:
    from zerver.context_processors import common_context
    if settings.WELCOME_EMAIL_SENDER is not None:
        # line break to avoid triggering lint rule
        from_name = settings.WELCOME_EMAIL_SENDER['name']
        from_address = settings.WELCOME_EMAIL_SENDER['email']
    else:
        from_name = None
        from_address = FromAddress.SUPPORT

    unsubscribe_link = one_click_unsubscribe_link(user, "welcome")
    context = common_context(user)
    context.update({
        'unsubscribe_link': unsubscribe_link,
        'organization_setup_advice_link':
        user.realm.uri + '/help/getting-your-organization-started-with-zulip',
        'is_realm_admin': user.is_realm_admin,
    })
    send_future_email(
        "zerver/emails/followup_day1", user.realm, to_user_id=user.id, from_name=from_name,
        from_address=from_address, context=context)
    send_future_email(
        "zerver/emails/followup_day2", user.realm, to_user_id=user.id, from_name=from_name,
        from_address=from_address, context=context, delay=followup_day2_email_delay(user))

def convert_html_to_markdown(html: Text) -> Text:
    # On Linux, the tool installs as html2markdown, and there's a command called
    # html2text that does something totally different. On OSX, the tool installs
    # as html2text.
    commands = ["html2markdown", "html2text"]

    for command in commands:
        try:
            # A body width of 0 means do not try to wrap the text for us.
            p = subprocess.Popen(
                [command, "--body-width=0"], stdout=subprocess.PIPE,
                stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
            break
        except OSError:
            continue

    markdown = p.communicate(input=html.encode('utf-8'))[0].decode('utf-8').strip()
    # We want images to get linked and inline previewed, but html2text will turn
    # them into links of the form `![](http://foo.com/image.png)`, which is
    # ugly. Run a regex over the resulting description, turning links of the
    # form `![](http://foo.com/image.png?12345)` into
    # `[image.png](http://foo.com/image.png)`.
    return re.sub("!\\[\\]\\((\\S*)/(\\S*)\\?(\\S*)\\)",
                  "[\\2](\\1/\\2)", markdown)

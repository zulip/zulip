from __future__ import print_function

from typing import cast, Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Text

import mandrill
from confirmation.models import Confirmation
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils import timezone
from zerver.decorator import statsd_increment, uses_mandrill
from zerver.lib.queue import queue_json_publish
from zerver.models import (
    Recipient,
    ScheduledJob,
    UserMessage,
    Stream,
    get_display_recipient,
    UserProfile,
    get_user_profile_by_email,
    get_user_profile_by_id,
    receives_offline_notifications,
    get_context_for_message,
    Message,
    Realm,
)

import datetime
import re
import subprocess
import ujson
from six.moves import urllib
from collections import defaultdict

def unsubscribe_token(user_profile):
    # type: (UserProfile) -> Text
    # Leverage the Django confirmations framework to generate and track unique
    # unsubscription tokens.
    return Confirmation.objects.get_link_for_object(user_profile).split("/")[-1]

def one_click_unsubscribe_link(user_profile, endpoint):
    # type: (UserProfile, Text) -> Text
    """
    Generate a unique link that a logged-out user can visit to unsubscribe from
    Zulip e-mails without having to first log in.
    """
    token = unsubscribe_token(user_profile)
    resource_path = "accounts/unsubscribe/%s/%s" % (endpoint, token)
    return "%s/%s" % (user_profile.realm.uri.rstrip("/"), resource_path)

def hashchange_encode(string):
    # type: (Text) -> Text
    # Do the same encoding operation as hashchange.encodeHashComponent on the
    # frontend.
    # `safe` has a default value of "/", but we want those encoded, too.
    return urllib.parse.quote(
        string.encode("utf-8"), safe=b"").replace(".", "%2E").replace("%", ".")

def pm_narrow_url(realm, participants):
    # type: (Realm, List[Text]) -> Text
    participants.sort()
    base_url = u"%s/#narrow/pm-with/" % (realm.uri,)
    return base_url + hashchange_encode(",".join(participants))

def stream_narrow_url(realm, stream):
    # type: (Realm, Text) -> Text
    base_url = u"%s/#narrow/stream/" % (realm.uri,)
    return base_url + hashchange_encode(stream)

def topic_narrow_url(realm, stream, topic):
    # type: (Realm, Text, Text) -> Text
    base_url = u"%s/#narrow/stream/" % (realm.uri,)
    return u"%s%s/topic/%s" % (base_url, hashchange_encode(stream),
                               hashchange_encode(topic))

def build_message_list(user_profile, messages):
    # type: (UserProfile, List[Message]) -> List[Dict[str, Any]]
    """
    Builds the message list object for the missed message email template.
    The messages are collapsed into per-recipient and per-sender blocks, like
    our web interface
    """
    messages_to_render = [] # type: List[Dict[str, Any]]

    def sender_string(message):
        # type: (Message) -> Text
        if message.recipient.type in (Recipient.STREAM, Recipient.HUDDLE):
            return message.sender.full_name
        else:
            return ''

    def relative_to_full_url(content):
        # type: (Text) -> Text
        # URLs for uploaded content are of the form
        # "/user_uploads/abc.png". Make them full paths.
        #
        # There's a small chance of colliding with non-Zulip URLs containing
        # "/user_uploads/", but we don't have much information about the
        # structure of the URL to leverage.
        content = re.sub(
            r"/user_uploads/(\S*)",
            user_profile.realm.uri + r"/user_uploads/\1", content)

        # Our proxying user-uploaded images seems to break inline images in HTML
        # emails, so scrub the image but leave the link.
        content = re.sub(
            r"<img src=(\S+)/user_uploads/(\S+)>", "", content)

        # URLs for emoji are of the form
        # "static/generated/emoji/images/emoji/snowflake.png".
        content = re.sub(
            r"/static/generated/emoji/images/emoji/",
            user_profile.realm.uri + r"/static/generated/emoji/images/emoji/",
            content)

        return content

    def fix_plaintext_image_urls(content):
        # type: (Text) -> Text
        # Replace image URLs in plaintext content of the form
        #     [image name](image url)
        # with a simple hyperlink.
        return re.sub(r"\[(\S*)\]\((\S*)\)", r"\2", content)

    def fix_emoji_sizes(html):
        # type: (Text) -> Text
        return html.replace(' class="emoji"', ' height="20px"')

    def build_message_payload(message):
        # type: (Message) -> Dict[str, Text]
        plain = message.content
        plain = fix_plaintext_image_urls(plain)
        plain = relative_to_full_url(plain)

        html = message.rendered_content
        html = relative_to_full_url(html)
        html = fix_emoji_sizes(html)

        return {'plain': plain, 'html': html}

    def build_sender_payload(message):
        # type: (Message) -> Dict[str, Any]
        sender = sender_string(message)
        return {'sender': sender,
                'content': [build_message_payload(message)]}

    def message_header(user_profile, message):
        # type: (UserProfile, Message) -> Dict[str, Any]
        disp_recipient = get_display_recipient(message.recipient)
        if message.recipient.type == Recipient.PERSONAL:
            header = u"You and %s" % (message.sender.full_name,)
            html_link = pm_narrow_url(user_profile.realm, [message.sender.email])
            header_html = u"<a style='color: #ffffff;' href='%s'>%s</a>" % (html_link, header)
        elif message.recipient.type == Recipient.HUDDLE:
            assert not isinstance(disp_recipient, Text)
            other_recipients = [r['full_name'] for r in disp_recipient
                                if r['email'] != user_profile.email]
            header = u"You and %s" % (", ".join(other_recipients),)
            html_link = pm_narrow_url(user_profile.realm, [r["email"] for r in disp_recipient
                                      if r["email"] != user_profile.email])
            header_html = u"<a style='color: #ffffff;' href='%s'>%s</a>" % (html_link, header)
        else:
            assert isinstance(disp_recipient, Text)
            header = u"%s > %s" % (disp_recipient, message.topic_name())
            stream_link = stream_narrow_url(user_profile.realm, disp_recipient)
            topic_link = topic_narrow_url(user_profile.realm, disp_recipient, message.subject)
            header_html = u"<a href='%s'>%s</a> > <a href='%s'>%s</a>" % (
                stream_link, disp_recipient, topic_link, message.subject)
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
def do_send_missedmessage_events_reply_in_zulip(user_profile, missed_messages, message_count):
    # type: (UserProfile, List[Message], int) -> None
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
    template_payload = common_context(user_profile)
    template_payload.update({
        'name': user_profile.full_name,
        'messages': build_message_list(user_profile, missed_messages),
        'message_count': message_count,
        'reply_warning': False,
        'mention': missed_messages[0].recipient.type == Recipient.STREAM,
        'reply_to_zulip': True,
        'unsubscribe_link': unsubscribe_link,
    })

    headers = {}
    from zerver.lib.email_mirror import create_missed_message_address
    address = create_missed_message_address(user_profile, missed_messages[0])
    headers['Reply-To'] = address

    senders = set(m.sender.full_name for m in missed_messages)
    sender_str = ", ".join(senders)
    plural_messages = 's' if len(missed_messages) > 1 else ''

    subject = "Missed Zulip%s from %s" % (plural_messages, sender_str)
    from_email = 'Zulip <%s>' % (settings.NOREPLY_EMAIL_ADDRESS,)
    if len(senders) == 1 and settings.SEND_MISSED_MESSAGE_EMAILS_AS_USER:
        # If this setting is enabled, you can reply to the Zulip
        # missed message emails directly back to the original sender.
        # However, one must ensure the Zulip server is in the SPF
        # record for the domain, or there will be spam/deliverability
        # problems.
        headers['Sender'] = from_email
        sender = missed_messages[0].sender
        from_email = '"%s" <%s>' % (sender_str, sender.email)

    text_content = loader.render_to_string('zerver/missed_message_email.txt', template_payload)
    html_content = loader.render_to_string('zerver/missed_message_email.html', template_payload)
    email_content = {
        'subject': subject,
        'text_content': text_content,
        'html_content': html_content,
        'from_email': from_email,
        'to': [user_profile.email],
        'headers': headers
    }
    queue_json_publish("missedmessage_email_senders", email_content, send_missedmessage_email)

    user_profile.last_reminder = timezone.now()
    user_profile.save(update_fields=['last_reminder'])


def send_missedmessage_email(data):
    # type: (Mapping[str, Any]) -> None
    msg = EmailMultiAlternatives(
        data.get('subject'),
        data.get('text_content'),
        data.get('from_email'),
        data.get('to'),
        headers=data.get('headers'))
    msg.attach_alternative(data.get('html_content'), "text/html")
    msg.send()


def handle_missedmessage_emails(user_profile_id, missed_email_events):
    # type: (int, Iterable[Dict[str, Any]]) -> None
    message_ids = [event.get('message_id') for event in missed_email_events]

    user_profile = get_user_profile_by_id(user_profile_id)
    if not receives_offline_notifications(user_profile):
        return

    messages = Message.objects.filter(usermessage__user_profile_id=user_profile,
                                      id__in=message_ids,
                                      usermessage__flags=~UserMessage.flags.read)
    if not messages:
        return

    messages_by_recipient_subject = defaultdict(list) # type: Dict[Tuple[int, Text], List[Message]]
    for msg in messages:
        messages_by_recipient_subject[(msg.recipient_id, msg.topic_name())].append(msg)

    message_count_by_recipient_subject = {
        recipient_subject: len(msgs)
        for recipient_subject, msgs in messages_by_recipient_subject.items()
    }

    for msg_list in messages_by_recipient_subject.values():
        msg = min(msg_list, key=lambda msg: msg.pub_date)
        if msg.recipient.type == Recipient.STREAM:
            msg_list.extend(get_context_for_message(msg))

    # Send an email per recipient subject pair
    for recipient_subject, msg_list in messages_by_recipient_subject.items():
        unique_messages = {m.id: m for m in msg_list}
        do_send_missedmessage_events_reply_in_zulip(
            user_profile,
            list(unique_messages.values()),
            message_count_by_recipient_subject[recipient_subject],
        )

@uses_mandrill
def clear_followup_emails_queue(email, mail_client=None):
    # type: (Text, Optional[mandrill.Mandrill]) -> None
    """
    Clear out queued emails (from Mandrill's queue) that would otherwise
    be sent to a specific email address. Optionally specify which sender
    to filter by (useful when there are more Zulip subsystems using our
    mandrill account).

    `email` is a string representing the recipient email
    `from_email` is a string representing the email account used
    to send the email (E.g. support@example.com).
    """
    # SMTP mail delivery implementation
    if not mail_client:
        items = ScheduledJob.objects.filter(type=ScheduledJob.EMAIL, filter_string__iexact = email)
        items.delete()
        return

    # Mandrill implementation
    for email_message in mail_client.messages.list_scheduled(to=email):
        result = mail_client.messages.cancel_scheduled(id=email_message["_id"])
        if result.get("status") == "error":
            print(result.get("name"), result.get("error"))
    return

def log_digest_event(msg):
    # type: (Text) -> None
    import logging
    logging.basicConfig(filename=settings.DIGEST_LOG_PATH, level=logging.INFO)
    logging.info(msg)

@uses_mandrill
def send_future_email(recipients, email_html, email_text, subject,
                      delay=datetime.timedelta(0), sender=None,
                      tags=[], mail_client=None):
    # type: (List[Dict[str, Any]], Text, Text, Text, datetime.timedelta, Optional[Dict[str, Text]], Iterable[Text], Optional[mandrill.Mandrill]) -> None
    """
    Sends email via Mandrill, with optional delay

    'mail_client' is filled in by the decorator
    """
    # When sending real emails while testing locally, don't accidentally send
    # emails to non-zulip.com users.
    if settings.DEVELOPMENT and \
       settings.EMAIL_BACKEND != 'django.core.mail.backends.console.EmailBackend':
        for recipient in recipients:
            email = recipient.get("email")
            if get_user_profile_by_email(email).realm.string_id != "zulip":
                raise ValueError("digest: refusing to send emails to non-zulip.com users.")

    # message = {"from_email": "othello@zulip.com",
    #            "from_name": "Othello",
    #            "html": "<p>hello</p> there",
    #            "tags": ["signup-reminders"],
    #            "to": [{'email':"acrefoot@zulip.com", 'name': "thingamajig"}]
    #            }

    # SMTP mail delivery implementation
    if not mail_client:
        if sender is None:
            # This may likely overridden by settings.DEFAULT_FROM_EMAIL
            sender = {'email': settings.NOREPLY_EMAIL_ADDRESS, 'name': 'Zulip'}
        for recipient in recipients:
            email_fields = {'email_html': email_html,
                            'email_subject': subject,
                            'email_text': email_text,
                            'recipient_email': recipient.get('email'),
                            'recipient_name': recipient.get('name'),
                            'sender_email': sender['email'],
                            'sender_name': sender['name']}
            ScheduledJob.objects.create(type=ScheduledJob.EMAIL, filter_string=recipient.get('email'),
                                        data=ujson.dumps(email_fields),
                                        scheduled_timestamp=timezone.now() + delay)
        return

    # Mandrill implementation
    if sender is None:
        sender = {'email': settings.NOREPLY_EMAIL_ADDRESS, 'name': 'Zulip'}

    message = {'from_email': sender['email'],
               'from_name': sender['name'],
               'to': recipients,
               'subject': subject,
               'html': email_html,
               'text': email_text,
               'tags': tags,
               }
    # ignore any delays smaller than 1-minute because it's cheaper just to sent them immediately
    if not isinstance(delay, datetime.timedelta):
        raise TypeError("specified delay is of the wrong type: %s" % (type(delay),))
    # Note: In the next section we hackishly use **{"async": False} to
    # work around https://github.com/python/mypy/issues/2959 "# type: ignore" doesn't work
    if delay < datetime.timedelta(minutes=1):
        results = mail_client.messages.send(message=message, ip_pool="Main Pool", **{"async": False})
    else:
        send_time = (timezone.now() + delay).__format__("%Y-%m-%d %H:%M:%S")
        results = mail_client.messages.send(message=message, ip_pool="Main Pool",
                                            send_at=send_time, **{"async": False})
    problems = [result for result in results if (result['status'] in ('rejected', 'invalid'))]

    if problems:
        for problem in problems:
            if problem["status"] == "rejected":
                if problem["reject_reason"] == "hard-bounce":
                    # A hard bounce means the address doesn't exist or the
                    # recipient mail server is completely blocking
                    # delivery. Don't try to send further emails.
                    if "digest-emails" in tags:
                        from zerver.lib.actions import do_change_enable_digest_emails
                        bounce_email = problem["email"]
                        user_profile = get_user_profile_by_email(bounce_email)
                        do_change_enable_digest_emails(user_profile, False)
                        log_digest_event("%s\nTurned off digest emails for %s" % (
                            str(problems), bounce_email))
                        continue
                elif problem["reject_reason"] == "soft-bounce":
                    # A soft bounce is temporary; let it try to resolve itself.
                    continue
            raise Exception(
                "While sending email (%s), encountered problems with these recipients: %r"
                % (subject, problems))
    return

def send_local_email_template_with_delay(recipients, template_prefix,
                                         template_payload, delay,
                                         tags=[], sender={'email': settings.NOREPLY_EMAIL_ADDRESS, 'name': 'Zulip'}):
    # type: (List[Dict[str, Any]], Text, Dict[str, Text], datetime.timedelta, Iterable[Text], Dict[str, Text]) -> None
    html_content = loader.render_to_string(template_prefix + ".html", template_payload)
    text_content = loader.render_to_string(template_prefix + ".txt", template_payload)
    subject = loader.render_to_string(template_prefix + ".subject", template_payload).strip()

    send_future_email(recipients,
                      html_content,
                      text_content,
                      subject,
                      delay=delay,
                      sender=sender,
                      tags=tags)

def enqueue_welcome_emails(email, name):
    # type: (Text, Text) -> None
    from zerver.context_processors import common_context
    if settings.WELCOME_EMAIL_SENDER is not None:
        sender = settings.WELCOME_EMAIL_SENDER # type: Dict[str, Text]
    else:
        sender = {'email': settings.ZULIP_ADMINISTRATOR, 'name': 'Zulip'}

    user_profile = get_user_profile_by_email(email)
    unsubscribe_link = one_click_unsubscribe_link(user_profile, "welcome")
    template_payload = common_context(user_profile)
    template_payload.update({
        'verbose_support_offers': settings.VERBOSE_SUPPORT_OFFERS,
        'unsubscribe_link': unsubscribe_link
    })

    # Send day 1 email
    send_local_email_template_with_delay([{'email': email, 'name': name}],
                                         "zerver/emails/followup/day1",
                                         template_payload,
                                         datetime.timedelta(hours=1),
                                         tags=["followup-emails"],
                                         sender=sender)
    # Send day 2 email
    send_local_email_template_with_delay([{'email': email, 'name': name}],
                                         "zerver/emails/followup/day2",
                                         template_payload,
                                         datetime.timedelta(days=1),
                                         tags=["followup-emails"],
                                         sender=sender)

def convert_html_to_markdown(html):
    # type: (Text) -> Text
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
    return re.sub(u"!\\[\\]\\((\\S*)/(\\S*)\\?(\\S*)\\)",
                  u"[\\2](\\1/\\2)", markdown)

from confirmation.models import Confirmation
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from zerver.decorator import statsd_increment, uses_mandrill
from zerver.models import Recipient, ScheduledJob, UserMessage, \
    Stream, get_display_recipient, get_user_profile_by_email, \
    get_user_profile_by_id, receives_offline_notifications, \
    get_context_for_message

import datetime
import re
import subprocess
import ujson
import urllib
from collections import defaultdict

def unsubscribe_token(user_profile):
    # Leverage the Django confirmations framework to generate and track unique
    # unsubscription tokens.
    return Confirmation.objects.get_link_for_object(user_profile).split("/")[-1]

def one_click_unsubscribe_link(user_profile, endpoint):
    """
    Generate a unique link that a logged-out user can visit to unsubscribe from
    Zulip e-mails without having to first log in.
    """
    token = unsubscribe_token(user_profile)
    base_url = "https://" + settings.EXTERNAL_HOST
    resource_path = "accounts/unsubscribe/%s/%s" % (endpoint, token)
    return "%s/%s" % (base_url.rstrip("/"), resource_path)

def hashchange_encode(string):
    # Do the same encoding operation as hashchange.encodeHashComponent on the
    # frontend.
    # `safe` has a default value of "/", but we want those encoded, too.
    return urllib.quote(
        string.encode("utf-8"), safe="").replace(".", "%2E").replace("%", ".")

def pm_narrow_url(participants):
    participants.sort()
    base_url = "https://%s/#narrow/pm-with/" % (settings.EXTERNAL_HOST,)
    return base_url + hashchange_encode(",".join(participants))

def stream_narrow_url(stream):
    base_url = "https://%s/#narrow/stream/" % (settings.EXTERNAL_HOST,)
    return base_url + hashchange_encode(stream)

def topic_narrow_url(stream, topic):
    base_url = "https://%s/#narrow/stream/" % (settings.EXTERNAL_HOST,)
    return "%s%s/topic/%s" % (base_url, hashchange_encode(stream),
                              hashchange_encode(topic))

def build_message_list(user_profile, messages):
    """
    Builds the message list object for the missed message email template.
    The messages are collapsed into per-recipient and per-sender blocks, like
    our web interface
    """
    messages_to_render = []

    def sender_string(message):
        sender = ''
        if message.recipient.type in (Recipient.STREAM, Recipient.HUDDLE):
            sender = message.sender.full_name
        return sender

    def relative_to_full_url(content):
        # URLs for uploaded content are of the form
        # "/user_uploads/abc.png". Make them full paths.
        #
        # There's a small chance of colliding with non-Zulip URLs containing
        # "/user_uploads/", but we don't have much information about the
        # structure of the URL to leverage.
        content = re.sub(
            r"/user_uploads/(\S*)",
            settings.EXTERNAL_HOST + r"/user_uploads/\1", content)

        # Our proxying user-uploaded images seems to break inline images in HTML
        # emails, so scrub the image but leave the link.
        content = re.sub(
            r"<img src=(\S+)/user_uploads/(\S+)>", "", content)

        # URLs for emoji are of the form
        # "static/third/gemoji/images/emoji/snowflake.png".
        content = re.sub(
            r"static/third/gemoji/images/emoji/",
            settings.EXTERNAL_HOST + r"/static/third/gemoji/images/emoji/",
            content)

        return content

    def fix_plaintext_image_urls(content):
        # Replace image URLs in plaintext content of the form
        #     [image name](image url)
        # with a simple hyperlink.
        return re.sub(r"\[(\S*)\]\((\S*)\)", r"\2", content)

    def fix_emoji_sizes(html):
        return html.replace(' class="emoji"', ' height="20px"')

    def build_message_payload(message):
        plain = message.content
        plain = fix_plaintext_image_urls(plain)
        plain = relative_to_full_url(plain)

        html = message.rendered_content
        html = relative_to_full_url(html)
        html = fix_emoji_sizes(html)

        return {'plain': plain, 'html': html}

    def build_sender_payload(message):
        sender = sender_string(message)
        return {'sender': sender,
                'content': [build_message_payload(message)]}

    def message_header(user_profile, message):
        disp_recipient = get_display_recipient(message.recipient)
        if message.recipient.type == Recipient.PERSONAL:
            header = "You and %s" % (message.sender.full_name)
            html_link = pm_narrow_url([message.sender.email])
            header_html = "<a style='color: #ffffff;' href='%s'>%s</a>" % (html_link, header)
        elif message.recipient.type == Recipient.HUDDLE:
            other_recipients = [r['full_name'] for r in disp_recipient
                                    if r['email'] != user_profile.email]
            header = "You and %s" % (", ".join(other_recipients),)
            html_link = pm_narrow_url([r["email"] for r in disp_recipient
                                       if r["email"] != user_profile.email])
            header_html = "<a style='color: #ffffff;' href='%s'>%s</a>" % (html_link, header)
        else:
            header = "%s > %s" % (disp_recipient, message.subject)
            stream_link = stream_narrow_url(disp_recipient)
            topic_link = topic_narrow_url(disp_recipient, message.subject)
            header_html = "<a href='%s'>%s</a> > <a href='%s'>%s</a>" % (
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
    # Disabled missedmessage emails internally
    if not user_profile.enable_offline_email_notifications:
        return

    recipients = set((msg.recipient_id, msg.subject) for msg in missed_messages)
    if len(recipients) != 1:
        raise ValueError(
            'All missed_messages must have the same recipient and subject %r' %
            recipients
        )

    template_payload = {
        'name': user_profile.full_name,
        'messages': build_message_list(user_profile, missed_messages),
        'message_count': message_count,
        'url': 'https://%s' % (settings.EXTERNAL_HOST,),
        'reply_warning': False,
        'external_host': settings.EXTERNAL_HOST,
        'mention':missed_messages[0].recipient.type == Recipient.STREAM,
        'reply_to_zulip': True,
    }

    headers = {}
    from zerver.lib.email_mirror import create_missed_message_address
    address = create_missed_message_address(user_profile, missed_messages[0])
    headers['Reply-To'] = address

    senders = set(m.sender.full_name for m in missed_messages)
    sender_str = ", ".join(senders)
    plural_messages = 's' if len(missed_messages) > 1 else ''

    subject = "Missed Zulip%s from %s" % (plural_messages, sender_str)
    from_email = "%s (via Zulip) <%s>" % (sender_str, settings.NOREPLY_EMAIL_ADDRESS)

    text_content = loader.render_to_string('zerver/missed_message_email.txt', template_payload)
    html_content = loader.render_to_string('zerver/missed_message_email_html.txt', template_payload)

    msg = EmailMultiAlternatives(subject, text_content, from_email, [user_profile.email],
                                 headers = headers)
    msg.attach_alternative(html_content, "text/html")
    msg.send()

    user_profile.last_reminder = datetime.datetime.now()
    user_profile.save(update_fields=['last_reminder'])

@statsd_increment("missed_message_reminders")
def do_send_missedmessage_events(user_profile, missed_messages, message_count):
    """
    Send a reminder email and/or push notifications to a user if she's missed some PMs by being offline

    `user_profile` is the user to send the reminder to
    `missed_messages` is a list of Message objects to remind about
    """
    # Disabled missedmessage emails internally
    if not user_profile.enable_offline_email_notifications:
        return

    senders = set(m.sender.full_name for m in missed_messages)
    sender_str = ", ".join(senders)
    plural_messages = 's' if len(missed_messages) > 1 else ''
    template_payload = {'name': user_profile.full_name,
                        'messages': build_message_list(user_profile, missed_messages),
                        'message_count': message_count,
                        'url': 'https://%s' % (settings.EXTERNAL_HOST,),
                        'reply_warning': False,
                        'external_host': settings.EXTERNAL_HOST}
    headers = {}
    if all(msg.recipient.type in (Recipient.HUDDLE, Recipient.PERSONAL)
            for msg in missed_messages):
        # If we have one huddle, set a reply-to to all of the members
        # of the huddle except the user herself
        disp_recipients = [", ".join(recipient['email']
                                for recipient in get_display_recipient(mesg.recipient)
                                    if recipient['email'] != user_profile.email)
                                 for mesg in missed_messages]
        if all(msg.recipient.type == Recipient.HUDDLE for msg in missed_messages) and \
            len(set(disp_recipients)) == 1:
            headers['Reply-To'] = disp_recipients[0]
        elif len(senders) == 1:
            headers['Reply-To'] = missed_messages[0].sender.email
        else:
            template_payload['reply_warning'] = True
    else:
        # There are some @-mentions mixed in with personals
        template_payload['mention'] = True
        template_payload['reply_warning'] = True
        headers['Reply-To'] = "Nobody <%s>" % (settings.NOREPLY_EMAIL_ADDRESS,)

    # Give users a one-click unsubscribe link they can use to stop getting
    # missed message emails without having to log in first.
    unsubscribe_link = one_click_unsubscribe_link(user_profile, "missed_messages")
    template_payload["unsubscribe_link"] = unsubscribe_link

    subject = "Missed Zulip%s from %s" % (plural_messages, sender_str)
    from_email = "%s (via Zulip) <%s>" % (sender_str, settings.NOREPLY_EMAIL_ADDRESS)

    text_content = loader.render_to_string('zerver/missed_message_email.txt', template_payload)
    html_content = loader.render_to_string('zerver/missed_message_email_html.txt', template_payload)

    msg = EmailMultiAlternatives(subject, text_content, from_email, [user_profile.email],
                                 headers = headers)
    msg.attach_alternative(html_content, "text/html")
    msg.send()

    user_profile.last_reminder = datetime.datetime.now()
    user_profile.save(update_fields=['last_reminder'])


def handle_missedmessage_emails(user_profile_id, missed_email_events):
    message_ids = [event.get('message_id') for event in missed_email_events]

    user_profile = get_user_profile_by_id(user_profile_id)
    if not receives_offline_notifications(user_profile):
        return

    messages = [um.message for um in UserMessage.objects.filter(user_profile=user_profile,
                                                                message__id__in=message_ids,
                                                                flags=~UserMessage.flags.read)]
    if not messages:
        return

    messages_by_recipient_subject = defaultdict(list)
    for msg in messages:
        messages_by_recipient_subject[(msg.recipient_id, msg.subject)].append(msg)

    mesage_count_by_recipient_subject = {
        recipient_subject: len(msgs)
        for recipient_subject, msgs in messages_by_recipient_subject.items()
    }

    for msg_list in messages_by_recipient_subject.values():
        msg = min(msg_list, key=lambda msg: msg.pub_date)
        if msg.recipient.type == Recipient.STREAM:
            msg_list.extend(get_context_for_message(msg))

    # Send an email per recipient subject pair
    if user_profile.realm.domain == 'zulip.com':
        for recipient_subject, msg_list in messages_by_recipient_subject.items():
            unique_messages = {m.id: m for m in msg_list}
            do_send_missedmessage_events_reply_in_zulip(
                user_profile,
                unique_messages.values(),
                mesage_count_by_recipient_subject[recipient_subject],
            )
    else:
        all_messages = [
            msg_
            for msg_list in messages_by_recipient_subject.values()
            for msg_ in msg_list
        ]
        unique_messages = {m.id: m for m in all_messages}
        do_send_missedmessage_events(
            user_profile,
            unique_messages.values(),
            len(messages),
        )

@uses_mandrill
def clear_followup_emails_queue(email, mail_client=None):
    """
    Clear out queued emails (from Mandrill's queue) that would otherwise
    be sent to a specific email address. Optionally specify which sender
    to filter by (useful when there are more Zulip subsystems using our
    mandrill account).

    `email` is a string representing the recipient email
    `from_email` is a string representing the zulip email account used
    to send the email (for example `support@zulip.com` or `signups@zulip.com`)
    """
    # SMTP mail delivery implementation
    if not mail_client:
        items = ScheduledJob.objects.filter(type=ScheduledJob.EMAIL, filter_string__iexact = email)
        items.delete()
        return

    # Mandrill implementation
    for email in mail_client.messages.list_scheduled(to=email):
        result = mail_client.messages.cancel_scheduled(id=email["_id"])
        if result.get("status") == "error":
            print result.get("name"), result.get("error")
    return

def log_digest_event(msg):
    import logging
    logging.basicConfig(filename=settings.DIGEST_LOG_PATH, level=logging.INFO)
    logging.info(msg)

@uses_mandrill
def send_future_email(recipients, email_html, email_text, subject,
                      delay=datetime.timedelta(0), sender=None,
                      tags=[], mail_client=None):
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
            if get_user_profile_by_email(email).realm.domain != "zulip.com":
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
                                        scheduled_timestamp=datetime.datetime.utcnow() + delay)
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
    if type(delay) is not datetime.timedelta:
        raise TypeError("specified delay is of the wrong type: %s" % (type(delay),))
    if delay < datetime.timedelta(minutes=1):
        results = mail_client.messages.send(message=message, async=False, ip_pool="Main Pool")
    else:
        send_time = (datetime.datetime.utcnow() + delay).__format__("%Y-%m-%d %H:%M:%S")
        results = mail_client.messages.send(message=message, async=False, ip_pool="Main Pool", send_at=send_time)
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
    html_content = loader.render_to_string(template_prefix + ".html", template_payload)
    text_content = loader.render_to_string(template_prefix + ".text", template_payload)
    subject = loader.render_to_string(template_prefix + ".subject", template_payload).strip()

    return send_future_email(recipients,
                             html_content,
                             text_content,
                             subject,
                             delay=delay,
                             sender=sender,
                             tags=tags)

def enqueue_welcome_emails(email, name):
    sender = {'email': 'wdaher@zulip.com', 'name': 'Waseem Daher'}
    if settings.VOYAGER:
        sender = {'email': settings.ZULIP_ADMINISTRATOR, 'name': 'Zulip'}

    user_profile = get_user_profile_by_email(email)
    unsubscribe_link = one_click_unsubscribe_link(user_profile, "welcome")

    template_payload = {'name': name,
                        'not_voyager': not settings.VOYAGER,
                        'external_host': settings.EXTERNAL_HOST,
                        'unsubscribe_link': unsubscribe_link}

    #Send day 1 email
    send_local_email_template_with_delay([{'email': email, 'name': name}],
                                         "zerver/emails/followup/day1",
                                         template_payload,
                                         datetime.timedelta(hours=1),
                                         tags=["followup-emails"],
                                         sender=sender)
    #Send day 2 email
    tomorrow = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    # 11 AM EDT
    tomorrow_morning = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, 15, 0)
    assert(datetime.datetime.utcnow() < tomorrow_morning)
    send_local_email_template_with_delay([{'email': email, 'name': name}],
                                         "zerver/emails/followup/day2",
                                         template_payload,
                                         tomorrow_morning - datetime.datetime.utcnow(),
                                         tags=["followup-emails"],
                                         sender=sender)

def convert_html_to_markdown(html):
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

    markdown = p.communicate(input=html.encode("utf-8"))[0].strip()
    # We want images to get linked and inline previewed, but html2text will turn
    # them into links of the form `![](http://foo.com/image.png)`, which is
    # ugly. Run a regex over the resulting description, turning links of the
    # form `![](http://foo.com/image.png?12345)` into
    # `[image.png](http://foo.com/image.png)`.
    return re.sub(r"!\[\]\((\S*)/(\S*)\?(\S*)\)",
                  r"[\2](\1/\2)", markdown).decode("utf-8")

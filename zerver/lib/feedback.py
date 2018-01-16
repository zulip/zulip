
from django.conf import settings
from django.core.mail import EmailMessage
from typing import Any, Mapping, Optional, Text

from zerver.lib.actions import internal_send_message
from zerver.lib.send_email import FromAddress
from zerver.lib.redis_utils import get_redis_client
from zerver.models import get_realm, get_system_bot, \
    UserProfile, Realm

import time

client = get_redis_client()

def has_enough_time_expired_since_last_message(sender_email: Text, min_delay: float) -> bool:
    # This function returns a boolean, but it also has the side effect
    # of noting that a new message was received.
    key = 'zilencer:feedback:%s' % (sender_email,)
    t = int(time.time())
    last_time = client.getset(key, t)  # type: Optional[bytes]
    if last_time is None:
        return True
    delay = t - int(last_time)
    return delay > min_delay

def get_ticket_number() -> int:
    num_file = '/var/tmp/.feedback-bot-ticket-number'
    try:
        ticket_number = int(open(num_file).read()) + 1
    except Exception:
        ticket_number = 1
    open(num_file, 'w').write('%d' % (ticket_number,))
    return ticket_number

def deliver_feedback_by_zulip(message: Mapping[str, Any]) -> None:
    subject = "%s" % (message["sender_email"],)

    if len(subject) > 60:
        subject = subject[:57].rstrip() + "..."

    content = ''
    sender_email = message['sender_email']

    # We generate ticket numbers if it's been more than a few minutes
    # since their last message.  This avoids some noise when people use
    # enter-send.
    need_ticket = has_enough_time_expired_since_last_message(sender_email, 180)

    if need_ticket:
        ticket_number = get_ticket_number()
        content += '\n~~~'
        content += '\nticket Z%03d (@support please ack)' % (ticket_number,)
        content += '\nsender: %s' % (message['sender_full_name'],)
        content += '\nemail: %s' % (sender_email,)
        if 'sender_realm_str' in message:
            content += '\nrealm: %s' % (message['sender_realm_str'],)
        content += '\n~~~'
        content += '\n\n'

    content += message['content']

    user_profile = get_system_bot(settings.FEEDBACK_BOT)
    internal_send_message(user_profile.realm, settings.FEEDBACK_BOT,
                          "stream", settings.FEEDBACK_STREAM, subject, content)

def handle_feedback(event: Mapping[str, Any]) -> None:
    if not settings.ENABLE_FEEDBACK:
        return
    if settings.FEEDBACK_EMAIL is not None:
        to_email = settings.FEEDBACK_EMAIL
        subject = "Zulip feedback from %s" % (event["sender_email"],)
        content = event["content"]
        from_email = '"%s" <%s>' % (event["sender_full_name"], FromAddress.SUPPORT)
        headers = {'Reply-To': '"%s" <%s>' % (event["sender_full_name"], event["sender_email"])}
        msg = EmailMessage(subject, content, from_email, [to_email], headers=headers)
        msg.send()
    if settings.FEEDBACK_STREAM is not None:
        deliver_feedback_by_zulip(event)

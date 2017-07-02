from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils.timezone import now as timezone_now
from zerver.models import UserProfile, ScheduledJob

import datetime
from email.utils import parseaddr, formataddr
import ujson

from typing import Any, Dict, Iterable, List, Mapping, Optional, Text

class FromAddress(object):
    SUPPORT = parseaddr(settings.ZULIP_ADMINISTRATOR)[1]
    NOREPLY = parseaddr(settings.NOREPLY_EMAIL_ADDRESS)[1]

def display_email(user):
    # type: (UserProfile) -> Text
    # Change to '%s <%s>' % (user.full_name, user.email) once
    # https://github.com/zulip/zulip/issues/4676 is resolved
    return user.email

# Intended only for test code
def build_email(template_prefix, to_email, from_name=None, from_address=None,
                reply_to_email=None, context={}):
    # type: (str, Text, Optional[Text], Optional[Text], Optional[Text], Dict[str, Any]) -> EmailMultiAlternatives
    context.update({
        'support_email': FromAddress.SUPPORT,
        'verbose_support_offers': settings.VERBOSE_SUPPORT_OFFERS,
    })
    subject = loader.render_to_string(template_prefix + '.subject',
                                      context=context, using='Jinja2_plaintext').strip()
    message = loader.render_to_string(template_prefix + '.txt',
                                      context=context, using='Jinja2_plaintext')
    html_message = loader.render_to_string(template_prefix + '.html', context)

    if from_name is None:
        from_name = "Zulip"
    if from_address is None:
        from_address = FromAddress.NOREPLY
    from_email = formataddr((from_name, from_address))
    reply_to = None
    if reply_to_email is not None:
        reply_to = [reply_to_email]

    mail = EmailMultiAlternatives(subject, message, from_email, [to_email], reply_to=reply_to)
    if html_message is not None:
        mail.attach_alternative(html_message, 'text/html')
    return mail

def send_email(template_prefix, to_email, from_name=None, from_address=None, reply_to_email=None, context={}):
    # type: (str, Text, Optional[Text], Optional[Text], Optional[Text], Dict[str, Any]) -> bool
    mail = build_email(template_prefix, to_email, from_name=from_name,
                       from_address=from_address, reply_to_email=reply_to_email, context=context)
    return mail.send() > 0

def send_email_to_user(template_prefix, user, from_name=None, from_address=None, context={}):
    # type: (str, UserProfile, Optional[Text], Optional[Text], Dict[str, Text]) -> bool
    return send_email(template_prefix, display_email(user), from_name=from_name,
                      from_address=from_address, context=context)

# Returns None instead of bool so that the type signature matches the third
# argument of zerver.lib.queue.queue_json_publish
def send_email_from_dict(email_dict):
    # type: (Mapping[str, Any]) -> None
    send_email(**dict(email_dict))

def send_future_email(template_prefix, to_email, from_name=None, from_address=None, context={},
                      delay=datetime.timedelta(0)):
    # type: (str, Text, Optional[Text], Optional[Text], Dict[str, Any], datetime.timedelta) -> None
    email_fields = {'template_prefix': template_prefix, 'to_email': to_email, 'from_name': from_name,
                    'from_address': from_address, 'context': context}
    ScheduledJob.objects.create(type=ScheduledJob.EMAIL, filter_string=parseaddr(to_email)[1],
                                data=ujson.dumps(email_fields),
                                scheduled_timestamp=timezone_now() + delay)

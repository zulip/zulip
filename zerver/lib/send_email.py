from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils.timezone import now as timezone_now
from zerver.models import UserProfile, ScheduledEmail, get_user_profile_by_id, \
    EMAIL_TYPES

import datetime
from email.utils import parseaddr, formataddr
import ujson

from typing import Any, Dict, Iterable, List, Mapping, Optional, Text

from zerver.lib.logging_util import create_logger

## Logging setup ##

logger = create_logger('zulip.send_email', settings.EMAIL_LOG_PATH, 'INFO')

class FromAddress(object):
    SUPPORT = parseaddr(settings.ZULIP_ADMINISTRATOR)[1]
    NOREPLY = parseaddr(settings.NOREPLY_EMAIL_ADDRESS)[1]

def build_email(template_prefix, to_user_id=None, to_email=None, from_name=None,
                from_address=None, reply_to_email=None, context=None):
    # type: (str, Optional[int], Optional[Text], Optional[Text], Optional[Text], Optional[Text], Optional[Dict[str, Any]]) -> EmailMultiAlternatives
    # Callers should pass exactly one of to_user_id and to_email.
    assert (to_user_id is None) ^ (to_email is None)
    if to_user_id is not None:
        to_user = get_user_profile_by_id(to_user_id)
        # Change to formataddr((to_user.full_name, to_user.email)) once
        # https://github.com/zulip/zulip/issues/4676 is resolved
        to_email = to_user.email

    if context is None:
        context = {}

    context.update({
        'realm_name_in_notifications': False,
        'support_email': FromAddress.SUPPORT,
        'verbose_support_offers': settings.VERBOSE_SUPPORT_OFFERS,
        'email_images_base_uri': settings.ROOT_DOMAIN_URI + '/static/images/emails/',
    })
    subject = loader.render_to_string(template_prefix + '.subject',
                                      context=context,
                                      using='Jinja2_plaintext').strip().replace('\n', '')
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
    # Remove the from_name in the reply-to for noreply emails, so that users
    # see "noreply@..." rather than "Zulip" or whatever the from_name is
    # when they reply in their email client.
    elif from_address == FromAddress.NOREPLY:
        reply_to = [FromAddress.NOREPLY]

    mail = EmailMultiAlternatives(subject, message, from_email, [to_email], reply_to=reply_to)
    if html_message is not None:
        mail.attach_alternative(html_message, 'text/html')
    return mail

class EmailNotDeliveredException(Exception):
    pass

# When changing the arguments to this function, you may need to write a
# migration to change or remove any emails in ScheduledEmail.
def send_email(template_prefix, to_user_id=None, to_email=None, from_name=None,
               from_address=None, reply_to_email=None, context={}):
    # type: (str, Optional[int], Optional[Text], Optional[Text], Optional[Text], Optional[Text], Dict[str, Any]) -> None
    mail = build_email(template_prefix, to_user_id=to_user_id, to_email=to_email, from_name=from_name,
                       from_address=from_address, reply_to_email=reply_to_email, context=context)
    template = template_prefix.split("/")[-1]
    logger.info("Sending %s email to %s" % (template, mail.to))

    if mail.send() == 0:
        logger.error("Error sending %s email to %s" % (template, mail.to))
        raise EmailNotDeliveredException

def send_email_from_dict(email_dict):
    # type: (Mapping[str, Any]) -> None
    send_email(**dict(email_dict))

def send_future_email(template_prefix, to_user_id=None, to_email=None, from_name=None,
                      from_address=None, context={}, delay=datetime.timedelta(0)):
    # type: (str, Optional[int], Optional[Text], Optional[Text], Optional[Text], Dict[str, Any], datetime.timedelta) -> None
    template_name = template_prefix.split('/')[-1]
    email_fields = {'template_prefix': template_prefix, 'to_user_id': to_user_id, 'to_email': to_email,
                    'from_name': from_name, 'from_address': from_address, 'context': context}

    assert (to_user_id is None) ^ (to_email is None)
    if to_user_id is not None:
        to_field = {'user_id': to_user_id}  # type: Dict[str, Any]
    else:
        to_field = {'address': parseaddr(to_email)[1]}

    ScheduledEmail.objects.create(
        type=EMAIL_TYPES[template_name],
        scheduled_timestamp=timezone_now() + delay,
        data=ujson.dumps(email_fields),
        **to_field)

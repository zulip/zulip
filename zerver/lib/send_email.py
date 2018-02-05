from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils.timezone import now as timezone_now
from django.template.exceptions import TemplateDoesNotExist
from zerver.models import UserProfile, ScheduledEmail, get_user_profile_by_id, \
    EMAIL_TYPES, Realm

import datetime
from email.utils import parseaddr, formataddr
import logging
import ujson

import os
from typing import Any, Dict, Iterable, List, Mapping, Optional, Text

from zerver.lib.logging_util import log_to_file

## Logging setup ##

logger = logging.getLogger('zulip.send_email')
log_to_file(logger, settings.EMAIL_LOG_PATH)

class FromAddress:
    SUPPORT = parseaddr(settings.ZULIP_ADMINISTRATOR)[1]
    NOREPLY = parseaddr(settings.NOREPLY_EMAIL_ADDRESS)[1]

def build_email(template_prefix: str, to_user_id: Optional[int]=None,
                to_email: Optional[Text]=None, from_name: Optional[Text]=None,
                from_address: Optional[Text]=None, reply_to_email: Optional[Text]=None,
                context: Optional[Dict[str, Any]]=None) -> EmailMultiAlternatives:
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
        'support_email': FromAddress.SUPPORT,
        'email_images_base_uri': settings.ROOT_DOMAIN_URI + '/static/images/emails',
        'physical_address': settings.PHYSICAL_ADDRESS,
    })
    subject = loader.render_to_string(template_prefix + '.subject',
                                      context=context,
                                      using='Jinja2_plaintext').strip().replace('\n', '')
    message = loader.render_to_string(template_prefix + '.txt',
                                      context=context, using='Jinja2_plaintext')

    try:
        html_message = loader.render_to_string(template_prefix + '.html', context)
    except TemplateDoesNotExist:
        emails_dir = os.path.dirname(template_prefix)
        template = os.path.basename(template_prefix)
        compiled_template_prefix = os.path.join(emails_dir, "compiled", template)
        html_message = loader.render_to_string(compiled_template_prefix + '.html', context)

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
def send_email(template_prefix: str, to_user_id: Optional[int]=None, to_email: Optional[Text]=None,
               from_name: Optional[Text]=None, from_address: Optional[Text]=None,
               reply_to_email: Optional[Text]=None, context: Dict[str, Any]={}) -> None:
    mail = build_email(template_prefix, to_user_id=to_user_id, to_email=to_email, from_name=from_name,
                       from_address=from_address, reply_to_email=reply_to_email, context=context)
    template = template_prefix.split("/")[-1]
    logger.info("Sending %s email to %s" % (template, mail.to))

    if mail.send() == 0:
        logger.error("Error sending %s email to %s" % (template, mail.to))
        raise EmailNotDeliveredException

def send_email_from_dict(email_dict: Mapping[str, Any]) -> None:
    send_email(**dict(email_dict))

def send_future_email(template_prefix: str, realm: Realm, to_user_id: Optional[int]=None,
                      to_email: Optional[Text]=None, from_name: Optional[Text]=None,
                      from_address: Optional[Text]=None, context: Dict[str, Any]={},
                      delay: datetime.timedelta=datetime.timedelta(0)) -> None:
    template_name = template_prefix.split('/')[-1]
    email_fields = {'template_prefix': template_prefix, 'to_user_id': to_user_id, 'to_email': to_email,
                    'from_name': from_name, 'from_address': from_address, 'context': context}

    if settings.DEVELOPMENT and not settings.TEST_SUITE:
        send_email(template_prefix, to_user_id=to_user_id, to_email=to_email, from_name=from_name,
                   from_address=from_address, context=context)
        # For logging the email

    assert (to_user_id is None) ^ (to_email is None)
    if to_user_id is not None:
        # The realm is redundant if we have a to_user_id; this assert just
        # expresses that fact
        assert(UserProfile.objects.filter(id=to_user_id, realm=realm).exists())
        to_field = {'user_id': to_user_id}  # type: Dict[str, Any]
    else:
        to_field = {'address': parseaddr(to_email)[1]}

    ScheduledEmail.objects.create(
        type=EMAIL_TYPES[template_name],
        scheduled_timestamp=timezone_now() + delay,
        realm=realm,
        data=ujson.dumps(email_fields),
        **to_field)

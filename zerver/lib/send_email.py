from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils.timezone import now as timezone_now
from django.utils.translation import override as override_language
from django.template.exceptions import TemplateDoesNotExist
from zerver.models import ScheduledEmail, get_user_profile_by_id, \
    EMAIL_TYPES, Realm

import datetime
from email.utils import parseaddr, formataddr
import logging
import ujson

import os
from typing import Any, Dict, List, Mapping, Optional, Tuple

from zerver.lib.logging_util import log_to_file
from confirmation.models import generate_key

## Logging setup ##

logger = logging.getLogger('zulip.send_email')
log_to_file(logger, settings.EMAIL_LOG_PATH)

class FromAddress:
    SUPPORT = parseaddr(settings.ZULIP_ADMINISTRATOR)[1]
    NOREPLY = parseaddr(settings.NOREPLY_EMAIL_ADDRESS)[1]

    # Generates an unpredictable noreply address.
    @staticmethod
    def tokenized_no_reply_address() -> str:
        if settings.ADD_TOKENS_TO_NOREPLY_ADDRESS:
            return parseaddr(settings.TOKENIZED_NOREPLY_EMAIL_ADDRESS)[1].format(token=generate_key())
        return FromAddress.NOREPLY

def build_email(template_prefix: str, to_user_ids: Optional[List[int]]=None,
                to_emails: Optional[List[str]]=None, from_name: Optional[str]=None,
                from_address: Optional[str]=None, reply_to_email: Optional[str]=None,
                language: Optional[str]=None, context: Optional[Dict[str, Any]]=None
                ) -> EmailMultiAlternatives:
    # Callers should pass exactly one of to_user_id and to_email.
    assert (to_user_ids is None) ^ (to_emails is None)
    if to_user_ids is not None:
        to_users = [get_user_profile_by_id(to_user_id) for to_user_id in to_user_ids]
        # Change to formataddr((to_user.full_name, to_user.email)) once
        # https://github.com/zulip/zulip/issues/4676 is resolved
        to_emails = [to_user.delivery_email for to_user in to_users]

    if context is None:
        context = {}

    context.update({
        'support_email': FromAddress.SUPPORT,
        'email_images_base_uri': settings.ROOT_DOMAIN_URI + '/static/images/emails',
        'physical_address': settings.PHYSICAL_ADDRESS,
    })

    def render_templates() -> Tuple[str, str, str]:
        email_subject = loader.render_to_string(template_prefix + '.subject.txt',
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
        return (html_message, message, email_subject)

    if not language and to_user_ids is not None:
        language = to_users[0].default_language
    if language:
        with override_language(language):
            # Make sure that we render the email using the target's native language
            (html_message, message, email_subject) = render_templates()
    else:
        (html_message, message, email_subject) = render_templates()
        logger.warning("Missing language for email template '{}'".format(template_prefix))

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

    mail = EmailMultiAlternatives(email_subject, message, from_email, to_emails, reply_to=reply_to)
    if html_message is not None:
        mail.attach_alternative(html_message, 'text/html')
    return mail

class EmailNotDeliveredException(Exception):
    pass

# When changing the arguments to this function, you may need to write a
# migration to change or remove any emails in ScheduledEmail.
def send_email(template_prefix: str, to_user_ids: Optional[List[int]]=None,
               to_emails: Optional[List[str]]=None, from_name: Optional[str]=None,
               from_address: Optional[str]=None, reply_to_email: Optional[str]=None,
               language: Optional[str]=None, context: Dict[str, Any]={}) -> None:
    mail = build_email(template_prefix, to_user_ids=to_user_ids, to_emails=to_emails,
                       from_name=from_name, from_address=from_address,
                       reply_to_email=reply_to_email, language=language, context=context)
    template = template_prefix.split("/")[-1]
    logger.info("Sending %s email to %s" % (template, mail.to))

    if mail.send() == 0:
        logger.error("Error sending %s email to %s" % (template, mail.to))
        raise EmailNotDeliveredException

def send_email_from_dict(email_dict: Mapping[str, Any]) -> None:
    send_email(**dict(email_dict))

def send_future_email(template_prefix: str, realm: Realm, to_user_ids: Optional[List[int]]=None,
                      to_emails: Optional[List[str]]=None, from_name: Optional[str]=None,
                      from_address: Optional[str]=None, language: Optional[str]=None,
                      context: Dict[str, Any]={}, delay: datetime.timedelta=datetime.timedelta(0)) -> None:
    template_name = template_prefix.split('/')[-1]
    email_fields = {'template_prefix': template_prefix, 'from_name': from_name, 'from_address': from_address,
                    'language': language, 'context': context}

    if settings.DEVELOPMENT_LOG_EMAILS:
        send_email(template_prefix, to_user_ids=to_user_ids, to_emails=to_emails, from_name=from_name,
                   from_address=from_address, language=language, context=context)
        # For logging the email

    assert (to_user_ids is None) ^ (to_emails is None)
    email = ScheduledEmail.objects.create(
        type=EMAIL_TYPES[template_name],
        scheduled_timestamp=timezone_now() + delay,
        realm=realm,
        data=ujson.dumps(email_fields))

    # We store the recipients in the ScheduledEmail object itself,
    # rather than the JSON data object, so that we can find and clear
    # them using clear_scheduled_emails.
    try:
        if to_user_ids is not None:
            email.users.add(*to_user_ids)
        else:
            assert to_emails is not None
            assert(len(to_emails) == 1)
            email.address = parseaddr(to_emails[0])[1]
        email.save()
    except Exception as e:
        email.delete()
        raise e

def send_email_to_admins(template_prefix: str, realm: Realm, from_name: Optional[str]=None,
                         from_address: Optional[str]=None, context: Dict[str, Any]={}) -> None:
    admins = realm.get_admin_users()
    admin_user_ids = [admin.id for admin in admins]
    send_email(template_prefix, to_user_ids=admin_user_ids, from_name=from_name,
               from_address=from_address, context=context)

def clear_scheduled_invitation_emails(email: str) -> None:
    """Unlike most scheduled emails, invitation emails don't have an
    existing user object to key off of, so we filter by address here."""
    items = ScheduledEmail.objects.filter(address__iexact=email,
                                          type=ScheduledEmail.INVITATION_REMINDER)
    items.delete()

def clear_scheduled_emails(user_ids: List[int], email_type: Optional[int]=None) -> None:
    items = ScheduledEmail.objects.filter(users__in=user_ids).distinct()
    if email_type is not None:
        items = items.filter(type=email_type)
    for item in items:
        item.users.remove(*user_ids)
        if item.users.all().count() == 0:
            item.delete()

def handle_send_email_format_changes(job: Dict[str, Any]) -> None:
    # Reformat any jobs that used the old to_email
    # and to_user_ids argument formats.
    if 'to_email' in job:
        if job['to_email'] is not None:
            job['to_emails'] = [job['to_email']]
        del job['to_email']
    if 'to_user_id' in job:
        if job['to_user_id'] is not None:
            job['to_user_ids'] = [job['to_user_id']]
        del job['to_user_id']

def deliver_email(email: ScheduledEmail) -> None:
    data = ujson.loads(email.data)
    if email.users.exists():
        data['to_user_ids'] = [user.id for user in email.users.all()]
    if email.address is not None:
        data['to_emails'] = [email.address]
    handle_send_email_format_changes(data)
    send_email(**data)
    email.delete()

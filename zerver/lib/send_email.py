import datetime
import hashlib
import logging
import os
from email.headerregistry import Address
from email.parser import Parser
from email.policy import default
from email.utils import formataddr, parseaddr
from typing import Any, Dict, List, Mapping, Optional, Tuple

import orjson
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management import CommandError
from django.template import loader
from django.template.exceptions import TemplateDoesNotExist
from django.utils.timezone import now as timezone_now
from django.utils.translation import override as override_language
from django.utils.translation import ugettext as _

from confirmation.models import generate_key
from scripts.setup.inline_email_css import inline_template
from zerver.lib.logging_util import log_to_file
from zerver.models import EMAIL_TYPES, Realm, ScheduledEmail, UserProfile, get_user_profile_by_id

## Logging setup ##

logger = logging.getLogger('zulip.send_email')
log_to_file(logger, settings.EMAIL_LOG_PATH)

class FromAddress:
    SUPPORT = parseaddr(settings.ZULIP_ADMINISTRATOR)[1]
    NOREPLY = parseaddr(settings.NOREPLY_EMAIL_ADDRESS)[1]

    support_placeholder = "SUPPORT"
    no_reply_placeholder = 'NO_REPLY'
    tokenized_no_reply_placeholder = 'TOKENIZED_NO_REPLY'

    # Generates an unpredictable noreply address.
    @staticmethod
    def tokenized_no_reply_address() -> str:
        if settings.ADD_TOKENS_TO_NOREPLY_ADDRESS:
            return parseaddr(settings.TOKENIZED_NOREPLY_EMAIL_ADDRESS)[1].format(token=generate_key())
        return FromAddress.NOREPLY

    @staticmethod
    def security_email_from_name(language: Optional[str]=None,
                                 user_profile: Optional[UserProfile]=None) -> str:
        if language is None:
            assert user_profile is not None
            language = user_profile.default_language

        with override_language(language):
            return _("Zulip Account Security")

def build_email(template_prefix: str, to_user_ids: Optional[List[int]]=None,
                to_emails: Optional[List[str]]=None, from_name: Optional[str]=None,
                from_address: Optional[str]=None, reply_to_email: Optional[str]=None,
                language: Optional[str]=None, context: Mapping[str, Any]={},
                realm: Optional[Realm]=None
                ) -> EmailMultiAlternatives:
    # Callers should pass exactly one of to_user_id and to_email.
    assert (to_user_ids is None) ^ (to_emails is None)
    if to_user_ids is not None:
        to_users = [get_user_profile_by_id(to_user_id) for to_user_id in to_user_ids]
        if realm is None:
            assert len({to_user.realm_id for to_user in to_users}) == 1
            realm = to_users[0].realm
        to_emails = [str(Address(display_name=to_user.full_name, addr_spec=to_user.delivery_email)) for to_user in to_users]

    extra_headers = {}
    if realm is not None:
        # formaddr is meant for formatting (display_name, email_address) pair for headers like "To",
        # but we can use its utility for formatting the List-Id header, as it follows the same format,
        # except having just a domain instead of an email address.
        extra_headers['List-Id'] = formataddr((realm.name, realm.host))

    context = {
        **context,
        'support_email': FromAddress.SUPPORT,
        'email_images_base_uri': settings.ROOT_DOMAIN_URI + '/static/images/emails',
        'physical_address': settings.PHYSICAL_ADDRESS,
    }

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
        logger.warning("Missing language for email template '%s'", template_prefix)

    if from_name is None:
        from_name = "Zulip"
    if from_address is None:
        from_address = FromAddress.NOREPLY
    if from_address == FromAddress.tokenized_no_reply_placeholder:
        from_address = FromAddress.tokenized_no_reply_address()
    if from_address == FromAddress.no_reply_placeholder:
        from_address = FromAddress.NOREPLY
    if from_address == FromAddress.support_placeholder:
        from_address = FromAddress.SUPPORT

    from_email = str(Address(display_name=from_name, addr_spec=from_address))
    reply_to = None
    if reply_to_email is not None:
        reply_to = [reply_to_email]
    # Remove the from_name in the reply-to for noreply emails, so that users
    # see "noreply@..." rather than "Zulip" or whatever the from_name is
    # when they reply in their email client.
    elif from_address == FromAddress.NOREPLY:
        reply_to = [FromAddress.NOREPLY]

    mail = EmailMultiAlternatives(email_subject, message, from_email, to_emails, reply_to=reply_to,
                                  headers=extra_headers)
    if html_message is not None:
        mail.attach_alternative(html_message, 'text/html')
    return mail

class EmailNotDeliveredException(Exception):
    pass

class DoubledEmailArgumentException(CommandError):
    def __init__(self, argument_name: str) -> None:
        msg = f"Argument '{argument_name}' is ambiguously present in both options and email template."
        super().__init__(msg)

class NoEmailArgumentException(CommandError):
    def __init__(self, argument_name: str) -> None:
        msg = f"Argument '{argument_name}' is required in either options or email template."
        super().__init__(msg)

# When changing the arguments to this function, you may need to write a
# migration to change or remove any emails in ScheduledEmail.
def send_email(template_prefix: str, to_user_ids: Optional[List[int]]=None,
               to_emails: Optional[List[str]]=None, from_name: Optional[str]=None,
               from_address: Optional[str]=None, reply_to_email: Optional[str]=None,
               language: Optional[str]=None, context: Dict[str, Any]={},
               realm: Optional[Realm]=None) -> None:
    mail = build_email(template_prefix, to_user_ids=to_user_ids, to_emails=to_emails,
                       from_name=from_name, from_address=from_address,
                       reply_to_email=reply_to_email, language=language, context=context,
                       realm=realm)
    template = template_prefix.split("/")[-1]
    logger.info("Sending %s email to %s", template, mail.to)

    if mail.send() == 0:
        logger.error("Error sending %s email to %s", template, mail.to)
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
        data=orjson.dumps(email_fields).decode())

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
                         from_address: Optional[str]=None, language: Optional[str]=None,
                         context: Dict[str, Any]={}) -> None:
    admins = realm.get_human_admin_users()
    admin_user_ids = [admin.id for admin in admins]
    send_email(template_prefix, to_user_ids=admin_user_ids, from_name=from_name,
               from_address=from_address, language=language, context=context)

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
    data = orjson.loads(email.data)
    if email.users.exists():
        data['to_user_ids'] = [user.id for user in email.users.all()]
    if email.address is not None:
        data['to_emails'] = [email.address]
    handle_send_email_format_changes(data)
    send_email(**data)
    email.delete()

def get_header(option: Optional[str], header: Optional[str], name: str) -> str:
    if option and header:
        raise DoubledEmailArgumentException(name)
    if not option and not header:
        raise NoEmailArgumentException(name)
    return str(option or header)

def send_custom_email(users: List[UserProfile], options: Dict[str, Any]) -> None:
    """
    Can be used directly with from a management shell with
    send_custom_email(user_profile_list, dict(
        markdown_template_path="/path/to/markdown/file.md",
        subject="Email Subject",
        from_name="Sender Name")
    )
    """

    with open(options["markdown_template_path"]) as f:
        text = f.read()
        parsed_email_template = Parser(policy=default).parsestr(text)
        email_template_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[0:32]

    email_filename = f"custom/custom_email_{email_template_hash}.source.html"
    email_id = f"zerver/emails/custom/custom_email_{email_template_hash}"
    markdown_email_base_template_path = "templates/zerver/emails/custom_email_base.pre.html"
    html_source_template_path = f"templates/{email_id}.source.html"
    plain_text_template_path = f"templates/{email_id}.txt"
    subject_path = f"templates/{email_id}.subject.txt"
    os.makedirs(os.path.dirname(html_source_template_path), exist_ok=True)

    # First, we render the Markdown input file just like our
    # user-facing docs with render_markdown_path.
    with open(plain_text_template_path, "w") as f:
        f.write(parsed_email_template.get_payload())

    from zerver.templatetags.app_filters import render_markdown_path
    rendered_input = render_markdown_path(plain_text_template_path.replace("templates/", ""))

    # And then extend it with our standard email headers.
    with open(html_source_template_path, "w") as f:
        with open(markdown_email_base_template_path) as base_template:
            # Note that we're doing a hacky non-Jinja2 substitution here;
            # we do this because the normal render_markdown_path ordering
            # doesn't commute properly with inline_email_css.
            f.write(base_template.read().replace('{{ rendered_input }}',
                                                 rendered_input))

    with open(subject_path, "w") as f:
        f.write(get_header(options.get("subject"),
                           parsed_email_template.get("subject"), "subject"))

    inline_template(email_filename)

    # Finally, we send the actual emails.
    for user_profile in users:
        if options.get('admins_only') and not user_profile.is_realm_admin:
            continue
        context = {
            'realm_uri': user_profile.realm.uri,
            'realm_name': user_profile.realm.name,
        }
        send_email(email_id, to_user_ids=[user_profile.id],
                   from_address=FromAddress.SUPPORT,
                   reply_to_email=options.get("reply_to"),
                   from_name=get_header(options.get("from_name"),
                                        parsed_email_template.get("from"),
                                        "from_name"),
                   context=context)

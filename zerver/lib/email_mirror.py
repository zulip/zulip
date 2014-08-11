from __future__ import absolute_import

import logging
import re

from email.header import decode_header

from django.conf import settings

from zerver.lib.actions import decode_email_address, internal_send_message
from zerver.lib.notifications import convert_html_to_markdown
from zerver.lib.redis_utils import get_redis_client
from zerver.lib.upload import upload_message_image
from zerver.lib.utils import generate_random_token
from zerver.models import Stream, Recipient, get_user_profile_by_email, \
    get_user_profile_by_id, get_display_recipient, get_recipient

logger = logging.getLogger(__name__)

def redact_stream(error_message):
    domain = settings.EMAIL_GATEWAY_PATTERN.rsplit('@')[-1]
    stream_match = re.search(r'\b(.*?)@' + domain, error_message)
    if stream_match:
        stream_name = stream_match.groups()[0]
        return error_message.replace(stream_name, "X" * len(stream_name))
    return error_message

def report_to_zulip(error_message):
    error_stream = Stream.objects.get(name="errors", realm__domain=settings.ADMIN_DOMAIN)
    send_zulip(error_stream, "email mirror error",
               """~~~\n%s\n~~~""" % (error_message,))

def log_and_report(email_message, error_message, debug_info):
    scrubbed_error = "Sender: %s\n%s" % (email_message.get("From"),
                                         redact_stream(error_message))

    if "to" in debug_info:
        scrubbed_error = "Stream: %s\n%s" % (redact_stream(debug_info["to"]),
                                             scrubbed_error)

    if "stream" in debug_info:
        scrubbed_error = "Realm: %s\n%s" % (debug_info["stream"].realm.domain,
                                            scrubbed_error)

    logger.error(scrubbed_error)
    report_to_zulip(scrubbed_error)


# Temporary missed message addresses

redis_client = get_redis_client()


def missed_message_redis_key(token):
    return 'missed_message:' + token


def is_missed_message_address(address):
    local_part = address.split('@')[0]
    return local_part.startswith('mm') and len(local_part) == 34


def get_missed_message_token_from_address(address):
    local_part = address.split('@')[0]
    if not address.startswith('mm') and len(address) != 34:
        raise ZulipEmailForwardError('Could not parse missed message address')
    return local_part[2:]


def create_missed_message_address(user_profile, message):
    if message.recipient.type == Recipient.PERSONAL:
        # We need to reply to the sender so look up their personal recipient_id
        recipient_id = get_recipient(Recipient.PERSONAL, message.sender_id).id
    else:
        recipient_id = message.recipient_id

    data = {
        'user_profile_id': user_profile.id,
        'recipient_id': recipient_id,
        'subject': message.subject,
    }

    while True:
        token = generate_random_token(32)
        key = missed_message_redis_key(token)
        if redis_client.hsetnx(key, 'uses_left', 1):
            break

    with redis_client.pipeline() as pipeline:
        pipeline.hmset(key, data)
        pipeline.expire(key, 60 * 60 * 24 * 5)
        pipeline.execute()

    address = 'mm' + token
    return settings.EMAIL_GATEWAY_PATTERN % (address, )


def mark_missed_message_address_as_used(address):
    token = get_missed_message_token_from_address(address)
    key = missed_message_redis_key(token)
    with redis_client.pipeline() as pipeline:
        pipeline.hincrby(key, 'uses_left', -1)
        pipeline.expire(key, 60 * 60 * 24 * 5)
        new_value = pipeline.execute()[0]
    if new_value < 0:
        redis_client.delete(key)
        raise ZulipEmailForwardError('Missed message address has already been used')


def send_to_missed_message_address(address, message):
    token = get_missed_message_token_from_address(address)
    key = missed_message_redis_key(token)
    result = redis_client.hmget(key, 'user_profile_id', 'recipient_id', 'subject')
    if not all(val is not None for val in result):
        raise ZulipEmailForwardError('Missing missed message address data')
    user_profile_id, recipient_id, subject = result

    user_profile = get_user_profile_by_id(user_profile_id)
    recipient = Recipient.objects.get(id=recipient_id)
    display_recipient = get_display_recipient(recipient)

    # Testing with basestring so we don't depend on the list return type from
    # get_display_recipient
    if not isinstance(display_recipient, basestring):
        display_recipient = ','.join([user['email'] for user in display_recipient])

    body = filter_footer(extract_body(message))
    body += extract_and_upload_attachments(message, user_profile.realm)
    if not body:
        body = '(No email body)'

    if recipient.type == Recipient.STREAM:
        recipient_type_name = 'stream'
    else:
        recipient_type_name = 'private'

    internal_send_message(user_profile.email, recipient_type_name,
                          display_recipient, subject, body)


## Sending the Zulip ##

class ZulipEmailForwardError(Exception):
    pass

def send_zulip(stream, topic, content):
    internal_send_message(
            settings.EMAIL_GATEWAY_BOT,
            "stream",
            stream.name,
            topic[:60],
            content[:2000],
            stream.realm)

def valid_stream(stream_name, token):
    try:
        stream = Stream.objects.get(email_token=token)
        return stream.name.lower() == stream_name.lower()
    except Stream.DoesNotExist:
        return False

def get_message_part_by_type(message, content_type):
    charsets = message.get_charsets()

    for idx, part in enumerate(message.walk()):
        if part.get_content_type() == content_type:
            content = part.get_payload(decode=True)
            if charsets[idx]:
                content = content.decode(charsets[idx], errors="ignore")
            return content

def extract_body(message):
    # If the message contains a plaintext version of the body, use
    # that.
    plaintext_content = get_message_part_by_type(message, "text/plain")
    if plaintext_content:
        return plaintext_content

    # If we only have an HTML version, try to make that look nice.
    html_content = get_message_part_by_type(message, "text/html")
    if html_content:
        return convert_html_to_markdown(html_content)

    raise ZulipEmailForwardError("Unable to find plaintext or HTML message body")

def filter_footer(text):
    # Try to filter out obvious footers.
    possible_footers = filter(lambda line: line.strip().startswith("--"),
                              text.split("\n"))
    if len(possible_footers) != 1:
        # Be conservative and don't try to scrub content if there
        # isn't a trivial footer structure.
        return text

    return text.partition("--")[0].strip()

def extract_and_upload_attachments(message, realm):
    user_profile = get_user_profile_by_email(settings.EMAIL_GATEWAY_BOT)
    attachment_links = []

    payload = message.get_payload()
    if not isinstance(payload, list):
        # This is not a multipart message, so it can't contain attachments.
        return ""

    for part in payload:
        content_type = part.get_content_type()
        filename = part.get_filename()
        if filename:
            s3_url = upload_message_image(filename, content_type,
                                          part.get_payload(decode=True),
                                          user_profile,
                                          target_realm=realm)
            formatted_link = "[%s](%s)" % (filename, s3_url)
            attachment_links.append(formatted_link)

    return "\n".join(attachment_links)

def extract_and_validate(email):
    try:
        stream_name, token = decode_email_address(email)
    except (TypeError, ValueError):
        raise ZulipEmailForwardError("Malformed email recipient " + email)

    if not valid_stream(stream_name, token):
        raise ZulipEmailForwardError("Bad stream token from email recipient " + email)

    return Stream.objects.get(email_token=token)

def find_emailgateway_recipient(message):
    # We can't use Delivered-To; if there is a X-Gm-Original-To
    # it is more accurate, so try to find the most-accurate
    # recipient list in descending priority order
    recipient_headers = ["X-Gm-Original-To", "Delivered-To", "To"]
    recipients = []
    for recipient_header in recipient_headers:
        r = message.get_all(recipient_header, None)
        if r:
            recipients = r
            break

    pattern_parts = [re.escape(part) for part in settings.EMAIL_GATEWAY_PATTERN.split('%s')]
    match_email_re = re.compile(".*?".join(pattern_parts))
    for recipient_email in recipients:
        if match_email_re.match(recipient_email):
            return recipient_email

    raise ZulipEmailForwardError("Missing recipient in mirror email")

def process_stream_message(to, subject, message, debug_info):
    stream = extract_and_validate(to)
    body = filter_footer(extract_body(message))
    body += extract_and_upload_attachments(message, stream.realm)
    debug_info["stream"] = stream
    if not body:
        # You can't send empty Zulips, so to avoid confusion over the
        # email forwarding failing, set a dummy message body.
        body = "(No email body)"
    send_zulip(stream, subject, body)

def process_missed_message(to, message, pre_checked):
    if not pre_checked:
        mark_missed_message_address_as_used(to)
    send_to_missed_message_address(to, message)

def process_message(message, rcpt_to=None, pre_checked=False):
    subject = decode_header(message.get("Subject", "(no subject)"))[0][0]

    debug_info = {}

    try:
        if rcpt_to is not None:
            to = rcpt_to
        else:
            to = find_emailgateway_recipient(message)
        debug_info["to"] = to

        if is_missed_message_address(to):
            process_missed_message(to, message, pre_checked)
        else:
            process_stream_message(to, subject, message, debug_info)
    except ZulipEmailForwardError, e:
        # TODO: notify sender of error, retry if appropriate.
        log_and_report(message, e.message, debug_info)

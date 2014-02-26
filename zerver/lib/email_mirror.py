from __future__ import absolute_import

import logging
import re

from email.header import decode_header

from django.conf import settings

from zerver.lib.actions import decode_email_address, internal_send_message
from zerver.lib.notifications import convert_html_to_markdown
from zerver.lib.upload import upload_message_image
from zerver.models import Stream

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
                                          settings.EMAIL_GATEWAY_BOT,
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

def process_message(message, rcpt_to=None):
    subject = decode_header(message.get("Subject", "(no subject)"))[0][0]

    debug_info = {}

    try:
        body = filter_footer(extract_body(message))
        if rcpt_to is not None:
            to = rcpt_to
        else:
            to = find_emailgateway_recipient(message)
        debug_info["to"] = to
        stream = extract_and_validate(to)
        debug_info["stream"] = stream
        body += extract_and_upload_attachments(message, stream.realm)
        if not body:
            # You can't send empty Zulips, so to avoid confusion over the
            # email forwarding failing, set a dummy message body.
            body = "(No email body)"
        send_zulip(stream, subject, body)
    except ZulipEmailForwardError, e:
        # TODO: notify sender of error, retry if appropriate.
        log_and_report(message, e.message, debug_info)

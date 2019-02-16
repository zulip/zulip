from typing import Any, Dict, Optional

import logging
import re

from email.header import decode_header, make_header
from email.utils import getaddresses
import email.message as message

from django.conf import settings

from zerver.lib.actions import decode_email_address, get_email_gateway_message_string_from_address, \
    internal_send_message, internal_send_private_message, \
    internal_send_stream_message, internal_send_huddle_message, \
    truncate_body, truncate_topic
from zerver.lib.notifications import convert_html_to_markdown
from zerver.lib.queue import queue_json_publish
from zerver.lib.redis_utils import get_redis_client
from zerver.lib.upload import upload_message_file
from zerver.lib.utils import generate_random_token
from zerver.lib.send_email import FromAddress
from zerver.models import Stream, Recipient, \
    get_user_profile_by_id, get_display_recipient, get_personal_recipient, \
    Message, Realm, UserProfile, get_system_bot, get_user, get_stream_by_id_in_realm

logger = logging.getLogger(__name__)

def redact_stream(error_message: str) -> str:
    domain = settings.EMAIL_GATEWAY_PATTERN.rsplit('@')[-1]
    stream_match = re.search('\\b(.*?)@' + domain, error_message)
    if stream_match:
        stream_name = stream_match.groups()[0]
        return error_message.replace(stream_name, "X" * len(stream_name))
    return error_message

def report_to_zulip(error_message: str) -> None:
    if settings.ERROR_BOT is None:
        return
    error_bot = get_system_bot(settings.ERROR_BOT)
    error_stream = Stream.objects.get(name="errors", realm=error_bot.realm)
    send_zulip(settings.ERROR_BOT, error_stream, "email mirror error",
               """~~~\n%s\n~~~""" % (error_message,))

def log_and_report(email_message: message.Message, error_message: str, debug_info: Dict[str, Any]) -> None:
    scrubbed_error = u"Sender: %s\n%s" % (email_message.get("From"),
                                          redact_stream(error_message))

    if "to" in debug_info:
        scrubbed_error = "Stream: %s\n%s" % (redact_stream(debug_info["to"]),
                                             scrubbed_error)

    if "stream" in debug_info:
        scrubbed_error = "Realm: %s\n%s" % (debug_info["stream"].realm.string_id,
                                            scrubbed_error)

    logger.error(scrubbed_error)
    report_to_zulip(scrubbed_error)


# Temporary missed message addresses

redis_client = get_redis_client()


def missed_message_redis_key(token: str) -> str:
    return 'missed_message:' + token


def is_missed_message_address(address: str) -> bool:
    msg_string = get_email_gateway_message_string_from_address(address)
    return is_mm_32_format(msg_string)

def is_mm_32_format(msg_string: Optional[str]) -> bool:
    '''
    Missed message strings are formatted with a little "mm" prefix
    followed by a randomly generated 32-character string.
    '''
    return msg_string is not None and msg_string.startswith('mm') and len(msg_string) == 34

def get_missed_message_token_from_address(address: str) -> str:
    msg_string = get_email_gateway_message_string_from_address(address)

    if msg_string is None:
        raise ZulipEmailForwardError('Address not recognized by gateway.')

    if not is_mm_32_format(msg_string):
        raise ZulipEmailForwardError('Could not parse missed message address')

    # strip off the 'mm' before returning the redis key
    return msg_string[2:]

def create_missed_message_address(user_profile: UserProfile, message: Message) -> str:
    if settings.EMAIL_GATEWAY_PATTERN == '':
        logger.warning("EMAIL_GATEWAY_PATTERN is an empty string, using "
                       "NOREPLY_EMAIL_ADDRESS in the 'from' field.")
        return FromAddress.NOREPLY

    if message.recipient.type == Recipient.PERSONAL:
        # We need to reply to the sender so look up their personal recipient_id
        recipient_id = get_personal_recipient(message.sender_id).id
    else:
        recipient_id = message.recipient_id

    data = {
        'user_profile_id': user_profile.id,
        'recipient_id': recipient_id,
        'subject': message.topic_name().encode('utf-8'),
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
    return settings.EMAIL_GATEWAY_PATTERN % (address,)


def mark_missed_message_address_as_used(address: str) -> None:
    token = get_missed_message_token_from_address(address)
    key = missed_message_redis_key(token)
    with redis_client.pipeline() as pipeline:
        pipeline.hincrby(key, 'uses_left', -1)
        pipeline.expire(key, 60 * 60 * 24 * 5)
        new_value = pipeline.execute()[0]
    if new_value < 0:
        redis_client.delete(key)
        raise ZulipEmailForwardError('Missed message address has already been used')

def construct_zulip_body(message: message.Message, realm: Realm) -> str:
    body = extract_body(message)
    # Remove null characters, since Zulip will reject
    body = body.replace("\x00", "")
    body = filter_footer(body)
    body += extract_and_upload_attachments(message, realm)
    body = body.strip()
    if not body:
        body = '(No email body)'
    return body

def send_to_missed_message_address(address: str, message: message.Message) -> None:
    token = get_missed_message_token_from_address(address)
    key = missed_message_redis_key(token)
    result = redis_client.hmget(key, 'user_profile_id', 'recipient_id', 'subject')
    if not all(val is not None for val in result):
        raise ZulipEmailForwardError('Missing missed message address data')
    user_profile_id, recipient_id, subject_b = result  # type: (bytes, bytes, bytes)

    user_profile = get_user_profile_by_id(user_profile_id)
    recipient = Recipient.objects.get(id=recipient_id)

    body = construct_zulip_body(message, user_profile.realm)

    if recipient.type == Recipient.STREAM:
        stream = get_stream_by_id_in_realm(recipient.type_id, user_profile.realm)
        internal_send_stream_message(
            user_profile.realm, user_profile, stream,
            subject_b.decode('utf-8'), body
        )
        recipient_str = stream.name
    elif recipient.type == Recipient.PERSONAL:
        display_recipient = get_display_recipient(recipient)
        assert not isinstance(display_recipient, str)
        recipient_str = display_recipient[0]['email']
        recipient_user = get_user(recipient_str, user_profile.realm)
        internal_send_private_message(user_profile.realm, user_profile,
                                      recipient_user, body)
    elif recipient.type == Recipient.HUDDLE:
        display_recipient = get_display_recipient(recipient)
        assert not isinstance(display_recipient, str)
        emails = [user_dict['email'] for user_dict in display_recipient]
        recipient_str = ', '.join(emails)
        internal_send_huddle_message(user_profile.realm, user_profile,
                                     emails, body)
    else:
        raise AssertionError("Invalid recipient type!")

    logger.info("Successfully processed email from %s to %s" % (
        user_profile.email, recipient_str))

## Sending the Zulip ##

class ZulipEmailForwardError(Exception):
    pass

class ZulipEmailForwardUserError(ZulipEmailForwardError):
    pass

def send_zulip(sender: str, stream: Stream, topic: str, content: str) -> None:
    internal_send_message(
        stream.realm,
        sender,
        "stream",
        stream.name,
        truncate_topic(topic),
        truncate_body(content),
        email_gateway=True)

def valid_stream(stream_name: str, token: str) -> bool:
    try:
        stream = Stream.objects.get(email_token=token)
        return stream.name.lower() == stream_name.lower()
    except Stream.DoesNotExist:
        return False

def get_message_part_by_type(message: message.Message, content_type: str) -> Optional[str]:
    charsets = message.get_charsets()

    for idx, part in enumerate(message.walk()):
        if part.get_content_type() == content_type:
            content = part.get_payload(decode=True)
            assert isinstance(content, bytes)
            if charsets[idx]:
                return content.decode(charsets[idx], errors="ignore")
    return None

talon_initialized = False
def extract_body(message: message.Message) -> str:
    import talon
    global talon_initialized
    if not talon_initialized:
        talon.init()
        talon_initialized = True

    # If the message contains a plaintext version of the body, use
    # that.
    plaintext_content = get_message_part_by_type(message, "text/plain")
    if plaintext_content:
        return talon.quotations.extract_from_plain(plaintext_content)

    # If we only have an HTML version, try to make that look nice.
    html_content = get_message_part_by_type(message, "text/html")
    if html_content:
        return convert_html_to_markdown(talon.quotations.extract_from_html(html_content))

    if plaintext_content is not None or html_content is not None:
        raise ZulipEmailForwardUserError("Email has no nonempty body sections; ignoring.")

    logging.warning("Content types: %s" % ([part.get_content_type() for part in message.walk()]))
    raise ZulipEmailForwardUserError("Unable to find plaintext or HTML message body")

def filter_footer(text: str) -> str:
    # Try to filter out obvious footers.
    possible_footers = [line for line in text.split("\n") if line.strip().startswith("--")]
    if len(possible_footers) != 1:
        # Be conservative and don't try to scrub content if there
        # isn't a trivial footer structure.
        return text

    return text.partition("--")[0].strip()

def extract_and_upload_attachments(message: message.Message, realm: Realm) -> str:
    user_profile = get_system_bot(settings.EMAIL_GATEWAY_BOT)
    attachment_links = []

    payload = message.get_payload()
    if not isinstance(payload, list):
        # This is not a multipart message, so it can't contain attachments.
        return ""

    for part in payload:
        content_type = part.get_content_type()
        filename = part.get_filename()
        if filename:
            attachment = part.get_payload(decode=True)
            if isinstance(attachment, bytes):
                s3_url = upload_message_file(filename, len(attachment), content_type,
                                             attachment,
                                             user_profile,
                                             target_realm=realm)
                formatted_link = "[%s](%s)" % (filename, s3_url)
                attachment_links.append(formatted_link)
            else:
                logger.warning("Payload is not bytes (invalid attachment %s in message from %s)." %
                               (filename, message.get("From")))

    return "\n".join(attachment_links)

def extract_and_validate(email: str) -> Stream:
    temp = decode_email_address(email)
    if temp is None:
        raise ZulipEmailForwardError("Malformed email recipient " + email)
    stream_name, token = temp

    if not valid_stream(stream_name, token):
        raise ZulipEmailForwardError("Bad stream token from email recipient " + email)

    return Stream.objects.get(email_token=token)

def find_emailgateway_recipient(message: message.Message) -> str:
    # We can't use Delivered-To; if there is a X-Gm-Original-To
    # it is more accurate, so try to find the most-accurate
    # recipient list in descending priority order
    recipient_headers = ["X-Gm-Original-To", "Delivered-To",
                         "Resent-To", "Resent-CC", "To", "CC"]

    pattern_parts = [re.escape(part) for part in settings.EMAIL_GATEWAY_PATTERN.split('%s')]
    match_email_re = re.compile(".*?".join(pattern_parts))

    header_addresses = [str(addr)
                        for recipient_header in recipient_headers
                        for addr in message.get_all(recipient_header, [])]

    for addr_tuple in getaddresses(header_addresses):
        if match_email_re.match(addr_tuple[1]):
            return addr_tuple[1]

    raise ZulipEmailForwardError("Missing recipient in mirror email")

def strip_from_subject(subject: str) -> str:
    # strips RE and FWD from the subject
    # from: https://stackoverflow.com/questions/9153629/regex-code-for-removing-fwd-re-etc-from-email-subject
    reg = r"([\[\(] *)?\b(RE|FWD?) *([-:;)\]][ :;\])-]*|$)|\]+ *$"
    stripped = re.sub(reg, "", subject, flags = re.IGNORECASE | re.MULTILINE)
    return stripped.strip()

def process_stream_message(to: str, subject: str, message: message.Message,
                           debug_info: Dict[str, Any]) -> None:
    stream = extract_and_validate(to)
    body = construct_zulip_body(message, stream.realm)
    debug_info["stream"] = stream
    send_zulip(settings.EMAIL_GATEWAY_BOT, stream, subject, body)
    logger.info("Successfully processed email to %s (%s)" % (
        stream.name, stream.realm.string_id))

def process_missed_message(to: str, message: message.Message, pre_checked: bool) -> None:
    if not pre_checked:
        mark_missed_message_address_as_used(to)
    send_to_missed_message_address(to, message)

def process_message(message: message.Message, rcpt_to: Optional[str]=None, pre_checked: bool=False) -> None:
    subject_header = make_header(decode_header(message.get("Subject", "")))
    subject = strip_from_subject(str(subject_header)) or "(no topic)"

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
    except ZulipEmailForwardError as e:
        if isinstance(e, ZulipEmailForwardUserError):
            # TODO: notify sender of error, retry if appropriate.
            logging.warning(str(e))
        else:
            log_and_report(message, str(e), debug_info)

def mirror_email_message(data: Dict[str, str]) -> Dict[str, str]:
    rcpt_to = data['recipient']
    if is_missed_message_address(rcpt_to):
        try:
            mark_missed_message_address_as_used(rcpt_to)
        except ZulipEmailForwardError:
            return {
                "status": "error",
                "msg": "5.1.1 Bad destination mailbox address: "
                       "Bad or expired missed message address."
            }
    else:
        try:
            extract_and_validate(rcpt_to)
        except ZulipEmailForwardError:
            return {
                "status": "error",
                "msg": "5.1.1 Bad destination mailbox address: "
                       "Please use the address specified in your Streams page."
            }
    queue_json_publish(
        "email_mirror",
        {
            "message": data['msg_text'],
            "rcpt_to": rcpt_to
        }
    )
    return {"status": "success"}

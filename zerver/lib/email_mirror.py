import logging
import re
import secrets
from email.headerregistry import Address, AddressHeader
from email.message import EmailMessage
from re import Match

from django.conf import settings
from django.utils.translation import gettext as _
from typing_extensions import override

from zerver.actions.message_send import (
    check_send_message,
    internal_send_group_direct_message,
    internal_send_private_message,
    internal_send_stream_message,
)
from zerver.lib.display_recipient import get_display_recipient
from zerver.lib.email_mirror_helpers import (
    ZulipEmailForwardError,
    ZulipEmailForwardUserError,
    decode_email_address,
    get_email_gateway_message_string_from_address,
)
from zerver.lib.email_notifications import convert_html_to_markdown
from zerver.lib.exceptions import JsonableError, RateLimitedError
from zerver.lib.message import normalize_body, truncate_content, truncate_topic
from zerver.lib.rate_limiter import RateLimitedObject
from zerver.lib.send_email import FromAddress
from zerver.lib.streams import access_stream_for_send_message
from zerver.lib.string_validation import is_character_printable
from zerver.lib.upload import upload_message_attachment
from zerver.models import (
    ChannelEmailAddress,
    Message,
    MissedMessageEmailAddress,
    Realm,
    Recipient,
    Stream,
    UserProfile,
)
from zerver.models.clients import get_client
from zerver.models.streams import StreamTopicsPolicyEnum, get_stream_by_id_in_realm
from zerver.models.users import get_system_bot, get_user_profile_by_id
from zproject.backends import is_user_active

logger = logging.getLogger(__name__)


def redact_email_address(error_message: str) -> str:
    if not settings.EMAIL_GATEWAY_EXTRA_PATTERN_HACK:
        domain = Address(addr_spec=settings.EMAIL_GATEWAY_PATTERN).domain
    else:
        domain = settings.EMAIL_GATEWAY_EXTRA_PATTERN_HACK.removeprefix("@")

    def redact(address_match: Match[str]) -> str:
        email_address = address_match[0]
        if is_missed_message_address(email_address):
            annotation = " <Missed message address>"
        else:
            try:
                target_stream_id = decode_stream_email_address(email_address)[0].channel_id
                annotation = f" <Address to stream id: {target_stream_id}>"
            except ZulipEmailForwardError:
                annotation = " <Invalid address>"

        return "X" * len(address_match[1]) + address_match[2] + annotation

    return re.sub(rf"\b(\S*?)(@{re.escape(domain)})", redact, error_message)


def log_error(
    email_message: EmailMessage, error_message: str, to: str | None
) -> None:
    recipient = to or "No recipient found"
    error_message = "Sender: {}\nTo: {}\n{}".format(
        email_message.get("From"), recipient, error_message
    )

    error_message = redact_email_address(error_message)
    logger.error(error_message)


def generate_missed_message_token() -> str:
    return "mm" + secrets.token_hex(16)


def is_missed_message_address(address: str) -> bool:
    try:
        msg_string = get_email_gateway_message_string_from_address(address)
    except ZulipEmailForwardError:
        return False

    return msg_string is not None and msg_string.startswith("mm") and len(msg_string) == 34


def is_mm_32_format(msg_string: str | None) -> bool:
    return msg_string is not None and msg_string.startswith("mm") and len(msg_string) == 34


def get_missed_message_token_from_address(address: str) -> str:
    msg_string = get_email_gateway_message_string_from_address(address)
    if not is_mm_32_format(msg_string):
        raise ZulipEmailForwardError("Could not parse missed message address")
    return msg_string


def get_usable_missed_message_address(address: str) -> MissedMessageEmailAddress:
    token = get_missed_message_token_from_address(address)
    try:
        return MissedMessageEmailAddress.objects.select_related(
            "user_profile",
            "user_profile__realm",
            "message",
            "message__sender",
            "message__recipient",
            "message__sender__recipient",
        ).get(email_token=token)
    except MissedMessageEmailAddress.DoesNotExist:
        raise ZulipEmailForwardError("Zulip notification reply address is invalid.")


def create_missed_message_address(user_profile: UserProfile, message: Message) -> str:
    if settings.EMAIL_GATEWAY_PATTERN == "":
        return FromAddress.NOREPLY

    mm_address = MissedMessageEmailAddress.objects.create(
        message=message,
        user_profile=user_profile,
        email_token=generate_missed_message_token(),
    )
    return str(mm_address)


def construct_zulip_body(
    message: EmailMessage,
    subject: str,
    realm: Realm,
    *,
    sender: UserProfile,
    show_sender: bool = False,
    include_quotes: bool = False,
    include_footer: bool = False,
    prefer_text: bool = True,
    subject_in_body: bool = False,
) -> str:
    body = extract_body(message, include_quotes, prefer_text)
    body = body.replace("\x00", "")

    if not include_footer:
        body = filter_footer(body)

    if not body.endswith("\n"):
        body += "\n"
    if not body.rstrip():
        body = "(No email body)"

    preamble = ""
    if show_sender:
        preamble = f"**From:** {message.get('From', '')}\n"
    if subject_in_body:
        preamble += f"**Subject:** {subject}\n"
    if preamble:
        preamble += "\n"

    postamble = extract_and_upload_attachments(message, realm, sender)
    if postamble:
        postamble = "\n" + postamble

    body = truncate_content(
        body,
        settings.MAX_MESSAGE_LENGTH - len(preamble) - len(postamble),
        "\n[message truncated]",
    )
    return preamble + body + postamble


def send_zulip(sender: UserProfile, stream: Stream, topic_name: str, content: str) -> None:
    internal_send_stream_message(
        sender,
        stream,
        truncate_topic(topic_name),
        normalize_body(content),
        email_gateway=True,
    )


def send_mm_reply_to_stream(
    user_profile: UserProfile, stream: Stream, topic_name: str, body: str
) -> None:
    try:
        check_send_message(
            sender=user_profile,
            client=get_client("Internal"),
            recipient_type_name="stream",
            message_to=[stream.id],
            topic_name=topic_name,
            message_content=body,
        )
    except JsonableError as error:
        error_message = _(
            "Error sending message to channel {channel_name} via message notification email reply:\n{error_message}"
        ).format(channel_name=stream.name, error_message=error.msg)
        internal_send_private_message(
            get_system_bot(settings.NOTIFICATION_BOT, user_profile.realm_id),
            user_profile,
            error_message,
        )


def get_message_part_by_type(message: EmailMessage, content_type: str) -> str | None:
    charsets = message.get_charsets()

    for idx, part in enumerate(message.walk()):
        if part.get_content_type() == content_type:
            content = part.get_payload(decode=True)
            assert isinstance(content, bytes)
            charset = charsets[idx]
            if charset is not None:
                try:
                    return content.decode(charset, errors="ignore")
                except LookupError:
                    pass
            return content.decode("us-ascii", errors="ignore")
    return None


def extract_body(
    message: EmailMessage, include_quotes: bool = False, prefer_text: bool = True
) -> str:
    plaintext = extract_plaintext_body(message, include_quotes)
    html = extract_html_body(message, include_quotes)

    if plaintext is None and html is None:
        raise ZulipEmailForwardUserError("Unable to find plaintext or HTML message body")
    if not plaintext and not html:
        raise ZulipEmailForwardUserError("Email has no nonempty body sections; ignoring.")

    return plaintext if prefer_text and plaintext else html if html else plaintext


talon_initialized = False


def extract_plaintext_body(message: EmailMessage, include_quotes: bool = False) -> str | None:
    import talon_core

    global talon_initialized
    if not talon_initialized:
        talon_core.init()
        talon_initialized = True

    content = get_message_part_by_type(message, "text/plain")
    if content is None:
        return None
    return content if include_quotes else talon_core.quotations.extract_from_plain(content)


def extract_html_body(message: EmailMessage, include_quotes: bool = False) -> str | None:
    import talon_core

    global talon_initialized
    if not talon_initialized:  # nocoverage
        talon_core.init()
        talon_initialized = True

    content = get_message_part_by_type(message, "text/html")
    if content is None:
        return None
    html = (
        content
        if include_quotes
        else talon_core.quotations.extract_from_html(content)
    )
    return convert_html_to_markdown(html)


def filter_footer(text: str) -> str:
    possible_footers = [line for line in text.split("\n") if line.strip() == "--"]
    if len(possible_footers) != 1:
        return text
    return re.split(r"^\s*--\s*$", text, maxsplit=1, flags=re.MULTILINE)[0].strip()


def extract_and_upload_attachments(message: EmailMessage, realm: Realm, sender: UserProfile) -> str:
    links = []
    for part in message.walk():
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            continue
        upload_url, filename = upload_message_attachment(
            filename,
            part.get_content_type(),
            payload,
            sender,
            target_realm=realm,
        )
        filename = re.sub(r"[\[\]]", "", filename)
        links.append(f"[{filename}]({upload_url})")
    return "\n".join(links)


def decode_stream_email_address(email: str) -> tuple[ChannelEmailAddress, dict[str, bool]]:
    token, options = decode_email_address(email)
    try:
        return (
            ChannelEmailAddress.objects.select_related(
                "channel", "sender", "creator", "realm"
            ).get(email_token=token),
            options,
        )
    except ChannelEmailAddress.DoesNotExist:
        raise ZulipEmailForwardError("Bad stream token from email recipient " + email)


def find_emailgateway_recipient(message: EmailMessage) -> str:
    headers = [
        "X-Gm-Original-To",
        "Delivered-To",
        "Envelope-To",
        "Resent-To",
        "Resent-CC",
        "To",
        "CC",
    ]

    parts = [re.escape(p) for p in settings.EMAIL_GATEWAY_PATTERN.split("%s")]
    regex = re.compile(r".*?".join(parts))

    for header in headers:
        for value in message.get_all(header, []):
            emails = (
                [addr.addr_spec for addr in value.addresses]
                if isinstance(value, AddressHeader)
                else [str(value)]
            )
            for email in emails:
                if regex.match(email):
                    return email
    raise ZulipEmailForwardError("Missing recipient in mirror email")


def strip_from_subject(subject: str) -> str:
    reg = r"([\[\(] *)?\b(RE|AW|SV|FWD?) *(\[\d+\])?([-:;)\]][ :;\])-]*|$)|\]+ *$"
    return re.sub(reg, "", subject, flags=re.IGNORECASE | re.MULTILINE).strip()


def is_forwarded(subject: str) -> bool:
    reg = r"([\[\(] *)?\b(FWD?) *([-:;)\]][ :;\])-]*|$)|\]+ *$"
    return bool(re.match(reg, subject, flags=re.IGNORECASE))


def check_access_for_channel_email_address(channel_email_address: ChannelEmailAddress) -> None:
    channel = channel_email_address.channel
    sender = (
        channel_email_address.creator
        if channel_email_address.sender.id
        == get_system_bot(settings.EMAIL_GATEWAY_BOT, channel.realm_id).id
        and channel_email_address.creator is not None
        else channel_email_address.sender
    )
    access_stream_for_send_message(sender, channel, forwarder_user_profile=None)


def process_stream_message(to: str, message: EmailMessage) -> None:
    subject_header = message.get("Subject", "")

    channel_email_address, options = decode_stream_email_address(to)
    channel = channel_email_address.channel
    sender = channel_email_address.sender
    realm = channel_email_address.realm

    try:
        check_access_for_channel_email_address(channel_email_address)
    except JsonableError:
        return

    if "include_quotes" not in options:
        options["include_quotes"] = is_forwarded(subject_header)

    subject = strip_from_subject(subject_header)
    subject = "".join(c for c in subject if is_character_printable(c))

    if channel.topics_policy == StreamTopicsPolicyEnum.empty_topic_only.value:
        topic = ""
        options["subject_in_body"] = True
    elif not subject:
        topic = _("Email with no subject")
    else:
        topic = subject

    body = construct_zulip_body(message, subject, realm, sender=sender, **options)
    send_zulip(sender, channel, topic, body)


def process_missed_message(to: str, message: EmailMessage) -> None:
    if message.get("Auto-Submitted", "") in ("auto-replied", "auto-generated"):
        return

    mm_address = get_usable_missed_message_address(to)
    mm_address.increment_times_used()

    user_profile = mm_address.user_profile
    topic_name = mm_address.message.topic_name()

    recipient = (
        mm_address.message.sender.recipient
        if mm_address.message.recipient.type == Recipient.PERSONAL
        else mm_address.message.recipient
    )

    if not is_user_active(user_profile):
        return

    body = construct_zulip_body(message, topic_name, user_profile.realm, sender=user_profile)

    if recipient.type == Recipient.STREAM:
        send_mm_reply_to_stream(
            user_profile,
            get_stream_by_id_in_realm(recipient.type_id, user_profile.realm),
            topic_name,
            body,
        )
    elif recipient.type == Recipient.PERSONAL:
        internal_send_private_message(
            user_profile,
            get_user_profile_by_id(recipient.type_id),
            body,
        )
    elif recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        display_recipient = get_display_recipient(recipient)
        emails = [u["email"] for u in display_recipient]
        try:
            internal_send_group_direct_message(
                user_profile.realm,
                user_profile,
                body,
                emails=emails,
            )
        except JsonableError as error:  # nocoverage
            if "no longer using Zulip" in error.msg:  # nocoverage
                logger.info(
                    "Ignoring deactivated user when processing missed-message email reply: %s",
                    error.msg,
                )
                return
            raise  # nocoverage


def process_message(message: EmailMessage, rcpt_to: str | None = None) -> None:
    to: str | None = None
    try:
        to = rcpt_to if rcpt_to is not None else find_emailgateway_recipient(message)
        if is_missed_message_address(to):
            process_missed_message(to, message)
        else:
            process_stream_message(to, message)
    except ZulipEmailForwardUserError as e:
        logger.info(e.args[0])
    except ZulipEmailForwardError as e:
        log_error(message, e.args[0], to)


def validate_to_address(address: str, rate_limit: bool = True) -> None:
    if is_missed_message_address(address):
        mm_address = get_usable_missed_message_address(address)
        if mm_address.message.recipient.type == Recipient.STREAM:
            access_stream_for_send_message(
                mm_address.user_profile,
                get_stream_by_id_in_realm(
                    mm_address.message.recipient.type_id,
                    mm_address.user_profile.realm,
                ),
                forwarder_user_profile=None,
            )
    else:
        channel_email = decode_stream_email_address(address)[0]
        if rate_limit:
            rate_limit_mirror_by_realm(channel_email.realm)
        check_access_for_channel_email_address(channel_email)


class RateLimitedRealmMirror(RateLimitedObject):
    def __init__(self, realm: Realm) -> None:
        self.realm = realm
        super().__init__()

    @override
    def key(self) -> str:
        return f"{type(self).__name__}:{self.realm.string_id}"

    @override
    def rules(self) -> list[tuple[int, int]]:
        return settings.RATE_LIMITING_MIRROR_REALM_RULES


def rate_limit_mirror_by_realm(recipient_realm: Realm) -> None:
    ratelimited, secs_to_freedom = RateLimitedRealmMirror(recipient_realm).rate_limit()
    if ratelimited:
        raise RateLimitedError(secs_to_freedom)

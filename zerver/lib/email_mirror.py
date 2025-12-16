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


def log_error(email_message: EmailMessage, error_message: str, to: str | None) -> None:
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

    return is_mm_32_format(msg_string)


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


def process_missed_message(to: str, message: EmailMessage) -> None:
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

    body = normalize_body(message.get_payload())

    if recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        display_recipient = get_display_recipient(recipient)
        emails = [user["email"] for user in display_recipient]

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
    to: str | None
    try:
        to = rcpt_to if rcpt_to is not None else find_emailgateway_recipient(message)

        if is_missed_message_address(to):
            process_missed_message(to, message)
    except ZulipEmailForwardUserError as e:
        logger.info(e.args[0])
    except ZulipEmailForwardError as e:
        log_error(message, e.args[0], to)


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

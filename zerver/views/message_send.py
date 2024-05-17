from email.headerregistry import Address
from typing import Dict, Iterable, Optional, Sequence, Union, cast

from django.core import validators
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.message_send import (
    check_send_message,
    compute_irc_user_fullname,
    compute_jabber_user_fullname,
    create_mirror_user_if_needed,
    extract_private_recipients,
    extract_stream_indicator,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.markdown import render_message_markdown
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.topic import REQ_topic
from zerver.lib.validator import check_bool, check_string_in, to_float
from zerver.lib.zcommand import process_zcommands
from zerver.lib.zephyr import compute_mit_user_fullname
from zerver.models import Client, Message, RealmDomain, UserProfile
from zerver.models.users import get_user_including_cross_realm


class InvalidMirrorInputError(Exception):
    pass


def create_mirrored_message_users(
    client: Client,
    user_profile: UserProfile,
    recipients: Iterable[str],
    sender: str,
    recipient_type_name: str,
) -> UserProfile:
    sender_email = sender.strip().lower()
    referenced_users = {sender_email}
    if recipient_type_name == "private":
        for email in recipients:
            referenced_users.add(email.lower())

    if client.name == "zephyr_mirror":
        user_check = same_realm_zephyr_user
        fullname_function = compute_mit_user_fullname
    elif client.name == "irc_mirror":
        user_check = same_realm_irc_user
        fullname_function = compute_irc_user_fullname
    elif client.name in ("jabber_mirror", "JabberMirror"):
        user_check = same_realm_jabber_user
        fullname_function = compute_jabber_user_fullname
    else:
        raise InvalidMirrorInputError("Unrecognized mirroring client")

    for email in referenced_users:
        # Check that all referenced users are in our realm:
        if not user_check(user_profile, email):
            raise InvalidMirrorInputError("At least one user cannot be mirrored")

    # Create users for the referenced users, if needed.
    for email in referenced_users:
        create_mirror_user_if_needed(user_profile.realm, email, fullname_function)

    sender_user_profile = get_user_including_cross_realm(sender_email, user_profile.realm)
    return sender_user_profile


def same_realm_zephyr_user(user_profile: UserProfile, email: str) -> bool:
    #
    # Are the sender and recipient both addresses in the same Zephyr
    # mirroring realm?  We have to handle this specially, inferring
    # the domain from the e-mail address, because the recipient may
    # not existing in Zulip and we may need to make a stub Zephyr
    # mirroring user on the fly.
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    domain = Address(addr_spec=email).domain.lower()

    # Assumes allow_subdomains=False for all RealmDomain's corresponding to
    # these realms.
    return (
        user_profile.realm.is_zephyr_mirror_realm
        and RealmDomain.objects.filter(realm=user_profile.realm, domain=domain).exists()
    )


def same_realm_irc_user(user_profile: UserProfile, email: str) -> bool:
    # Check whether the target email address is an IRC user in the
    # same realm as user_profile, i.e. if the domain were example.com,
    # the IRC user would need to be username@irc.example.com
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    domain = Address(addr_spec=email).domain.lower()
    if domain.startswith("irc."):
        domain = domain[len("irc.") :]

    # Assumes allow_subdomains=False for all RealmDomain's corresponding to
    # these realms.
    return RealmDomain.objects.filter(realm=user_profile.realm, domain=domain).exists()


def same_realm_jabber_user(user_profile: UserProfile, email: str) -> bool:
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    # If your Jabber users have a different email domain than the
    # Zulip users, this is where you would do any translation.
    domain = Address(addr_spec=email).domain.lower()

    # Assumes allow_subdomains=False for all RealmDomain's corresponding to
    # these realms.
    return RealmDomain.objects.filter(realm=user_profile.realm, domain=domain).exists()


@has_request_variables
def send_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    req_type: str = REQ("type", str_validator=check_string_in(Message.API_RECIPIENT_TYPES)),
    req_to: Optional[str] = REQ("to", default=None),
    req_sender: Optional[str] = REQ("sender", default=None, documentation_pending=True),
    forged_str: Optional[str] = REQ("forged", default=None, documentation_pending=True),
    topic_name: Optional[str] = REQ_topic(),
    message_content: str = REQ("content"),
    widget_content: Optional[str] = REQ(default=None, documentation_pending=True),
    local_id: Optional[str] = REQ(default=None),
    queue_id: Optional[str] = REQ(default=None),
    time: Optional[float] = REQ(default=None, converter=to_float, documentation_pending=True),
    read_by_sender: Optional[bool] = REQ(json_validator=check_bool, default=None),
) -> HttpResponse:
    recipient_type_name = req_type
    if recipient_type_name == "direct":
        # For now, use "private" from Message.API_RECIPIENT_TYPES.
        # TODO: Use "direct" here, as well as in events and
        # message (created, schdeduled, drafts) objects/dicts.
        recipient_type_name = "private"
    elif recipient_type_name == "channel":
        # For now, use "stream" from Message.API_RECIPIENT_TYPES.
        # TODO: Use "channel" here, as well as in events and
        # message (created, schdeduled, drafts) objects/dicts.
        recipient_type_name = "stream"

    # If req_to is None, then we default to an
    # empty list of recipients.
    message_to: Union[Sequence[int], Sequence[str]] = []

    if req_to is not None:
        if recipient_type_name == "stream":
            stream_indicator = extract_stream_indicator(req_to)

            # For legacy reasons check_send_message expects
            # a list of streams, instead of a single stream.
            #
            # Also, mypy can't detect that a single-item
            # list populated from a Union[int, str] is actually
            # a Union[Sequence[int], Sequence[str]].
            if isinstance(stream_indicator, int):
                message_to = [stream_indicator]
            else:
                message_to = [stream_indicator]
        else:
            message_to = extract_private_recipients(req_to)

    # Temporary hack: We're transitioning `forged` from accepting
    # `yes` to accepting `true` like all of our normal booleans.
    forged = forged_str is not None and forged_str in ["yes", "true"]

    client = RequestNotes.get_notes(request).client
    assert client is not None
    can_forge_sender = user_profile.can_forge_sender
    if forged and not can_forge_sender:
        raise JsonableError(_("User not authorized for this query"))

    realm = user_profile.realm

    if client.name in ["zephyr_mirror", "irc_mirror", "jabber_mirror", "JabberMirror"]:
        # Here's how security works for mirroring:
        #
        # For direct messages, the message must be (1) both sent and
        # received exclusively by users in your realm, and (2)
        # received by the forwarding user.
        #
        # For stream messages, the message must be (1) being forwarded
        # by an API superuser for your realm and (2) being sent to a
        # mirrored stream.
        #
        # The most important security checks are in
        # `create_mirrored_message_users` below, which checks the
        # same-realm constraint.
        if req_sender is None:
            raise JsonableError(_("Missing sender"))
        if recipient_type_name != "private" and not can_forge_sender:
            raise JsonableError(_("User not authorized for this query"))

        # For now, mirroring only works with recipient emails, not for
        # recipient user IDs.
        if not all(isinstance(to_item, str) for to_item in message_to):
            raise JsonableError(_("Mirroring not allowed with recipient user IDs"))

        # We need this manual cast so that mypy doesn't complain about
        # create_mirrored_message_users not being able to accept a Sequence[int]
        # type parameter.
        message_to = cast(Sequence[str], message_to)

        try:
            mirror_sender = create_mirrored_message_users(
                client, user_profile, message_to, req_sender, recipient_type_name
            )
        except InvalidMirrorInputError:
            raise JsonableError(_("Invalid mirrored message"))

        if client.name == "zephyr_mirror" and not user_profile.realm.is_zephyr_mirror_realm:
            raise JsonableError(_("Zephyr mirroring is not allowed in this organization"))
        sender = mirror_sender
    else:
        if req_sender is not None:
            raise JsonableError(_("Invalid mirrored message"))
        sender = user_profile

    if read_by_sender is None:
        # Legacy default: a message you sent from a non-API client is
        # automatically marked as read for yourself.
        read_by_sender = client.default_read_by_sender()

    data: Dict[str, int] = {}
    sent_message_result = check_send_message(
        sender,
        client,
        recipient_type_name,
        message_to,
        topic_name,
        message_content,
        forged=forged,
        forged_timestamp=time,
        forwarder_user_profile=user_profile,
        realm=realm,
        local_id=local_id,
        sender_queue_id=queue_id,
        widget_content=widget_content,
        read_by_sender=read_by_sender,
    )
    data["id"] = sent_message_result.message_id
    if sent_message_result.automatic_new_visibility_policy:
        data["automatic_new_visibility_policy"] = (
            sent_message_result.automatic_new_visibility_policy
        )
    return json_success(request, data=data)


@has_request_variables
def zcommand_backend(
    request: HttpRequest, user_profile: UserProfile, command: str = REQ("command")
) -> HttpResponse:
    return json_success(request, data=process_zcommands(command, user_profile))


@has_request_variables
def render_message_backend(
    request: HttpRequest, user_profile: UserProfile, content: str = REQ()
) -> HttpResponse:
    message = Message()
    message.sender = user_profile
    message.realm = user_profile.realm
    message.content = content
    client = RequestNotes.get_notes(request).client
    assert client is not None
    message.sending_client = client

    rendering_result = render_message_markdown(message, content, realm=user_profile.realm)
    return json_success(request, data={"rendered": rendering_result.rendered_content})

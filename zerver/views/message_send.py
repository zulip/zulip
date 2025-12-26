from collections.abc import Iterable, Sequence
from email.headerregistry import Address
from typing import Annotated, Any, Literal, cast

from django.core import validators
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json

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
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import (
    DOCUMENTATION_PENDING,
    ApiParamConfig,
    OptionalTopic,
    typed_endpoint,
)
from zerver.lib.zcommand import process_zcommands
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
        referenced_users.update(email.lower() for email in recipients)

    if client.name == "irc_mirror":
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


def same_realm_irc_user(user_profile: UserProfile, email: str) -> bool:
    # Check whether the target email address is an IRC user in the
    # same realm as user_profile, i.e. if the domain were example.com,
    # the IRC user would need to be username@irc.example.com
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    domain = Address(addr_spec=email).domain.lower()
    domain = domain.removeprefix("irc.")

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


@typed_endpoint
def send_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    forged_str: Annotated[
        str | None, ApiParamConfig("forged", documentation_status=DOCUMENTATION_PENDING)
    ] = None,
    local_id: str | None = None,
    message_content: Annotated[str, ApiParamConfig("content")],
    queue_id: str | None = None,
    read_by_sender: Json[bool] | None = None,
    req_sender: Annotated[
        str | None, ApiParamConfig("sender", documentation_status=DOCUMENTATION_PENDING)
    ] = None,
    req_to: Annotated[str | None, ApiParamConfig("to")] = None,
    req_type: Annotated[Literal["direct", "private", "stream", "channel"], ApiParamConfig("type")],
    time: Annotated[
        Json[float] | None, ApiParamConfig("time", documentation_status=DOCUMENTATION_PENDING)
    ] = None,
    topic_name: OptionalTopic = None,
    widget_content: Annotated[
        str | None, ApiParamConfig("widget_content", documentation_status=DOCUMENTATION_PENDING)
    ] = None,
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

    # If to is None, then we default to an
    # empty list of recipients.
    message_to: Sequence[int] | Sequence[str] = []

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

    if client.name in ["irc_mirror", "jabber_mirror", "JabberMirror"]:
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

        sender = mirror_sender
    else:
        if req_sender is not None:
            raise JsonableError(_("Invalid mirrored message"))
        sender = user_profile

    if read_by_sender is None:
        # Legacy default: a message you sent from a non-API client is
        # automatically marked as read for yourself.
        read_by_sender = client.default_read_by_sender()

    data: dict[str, Any] = {}
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
    if sent_message_result.message_url:
        data["message_url"] = sent_message_result.message_url
    if sent_message_result.message_link:
        data["message_link"] = sent_message_result.message_link
    if sent_message_result.automatic_new_visibility_policy:
        data["automatic_new_visibility_policy"] = (
            sent_message_result.automatic_new_visibility_policy
        )
    return json_success(request, data=data)


@typed_endpoint
def zcommand_backend(
    request: HttpRequest, user_profile: UserProfile, *, command: str
) -> HttpResponse:
    return json_success(request, data=process_zcommands(command, user_profile))


@typed_endpoint
def render_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    content: str,
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

from collections.abc import Sequence
from dataclasses import asdict
from typing import Annotated, Literal, TypedDict

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json, StringConstraints

from zerver.actions.message_send import (
    check_send_message,
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
from zerver.models import Message, UserProfile
from zerver.models.users import get_user_including_cross_realm


class SendMessageResponseData(TypedDict, total=False):
    id: int
    message_url: str
    message_link: str
    automatic_new_visibility_policy: int


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

    if req_sender is not None:
        # Forging the sender of a message is gated on the
        # `can_forge_sender` permission, which a server administrator
        # grants with `manage.py change_user_role`.  The forged sender
        # must be an existing user in the forging user's own
        # organization; the further access checks for the forged
        # message live in `access_stream_for_send_message` and
        # `get_recipient_from_user_profiles`.
        if not can_forge_sender:
            raise JsonableError(_("User not authorized for this query"))

        try:
            sender = get_user_including_cross_realm(req_sender.strip().lower(), realm)
        except UserProfile.DoesNotExist:
            raise JsonableError(_("No such user"))
    else:
        sender = user_profile

    if read_by_sender is None:
        # Legacy default: a message you sent from a non-API client is
        # automatically marked as read for yourself.
        read_by_sender = client.default_read_by_sender()

    data: SendMessageResponseData = {}
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
    data["message_url"] = sent_message_result.message_url
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
    return json_success(request, data=asdict(process_zcommands(command, user_profile)))


@typed_endpoint
def render_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    content: Annotated[str, StringConstraints(max_length=settings.MAX_MESSAGE_LENGTH)],
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

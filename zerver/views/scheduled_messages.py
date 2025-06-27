from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from pydantic import Json, NonNegativeInt

from zerver.actions.scheduled_messages import (
    check_schedule_message,
    delete_scheduled_message,
    edit_scheduled_message,
)
from zerver.lib.exceptions import DeliveryTimeNotInFutureError, JsonableError
from zerver.lib.recipient_parsing import extract_direct_message_recipient_ids, extract_stream_id
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.scheduled_messages import (
    get_undelivered_reminders,
    get_undelivered_scheduled_messages,
)
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.typed_endpoint import (
    ApiParamConfig,
    OptionalTopic,
    PathOnly,
    typed_endpoint,
    typed_endpoint_without_parameters,
)
from zerver.lib.typed_endpoint_validators import check_string_in_validator
from zerver.models import Message, UserProfile


@typed_endpoint_without_parameters
def fetch_scheduled_messages(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(
        request, data={"scheduled_messages": get_undelivered_scheduled_messages(user_profile)}
    )


@typed_endpoint_without_parameters
def fetch_reminders(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(request, data={"reminders": get_undelivered_reminders(user_profile)})


@typed_endpoint
def delete_scheduled_messages(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    scheduled_message_id: PathOnly[NonNegativeInt],
) -> HttpResponse:
    delete_scheduled_message(user_profile, scheduled_message_id)
    return json_success(request)


@typed_endpoint
def update_scheduled_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_content: Annotated[str | None, ApiParamConfig("content")] = None,
    req_type: Annotated[
        Annotated[str, check_string_in_validator(Message.API_RECIPIENT_TYPES)] | None,
        ApiParamConfig("type"),
    ] = None,
    scheduled_delivery_timestamp: Json[int] | None = None,
    scheduled_message_id: PathOnly[NonNegativeInt],
    to: Json[int | list[int]] | None = None,
    topic_name: OptionalTopic = None,
) -> HttpResponse:
    if (
        req_type is None
        and to is None
        and topic_name is None
        and message_content is None
        and scheduled_delivery_timestamp is None
    ):
        raise JsonableError(_("Nothing to change"))

    recipient_type_name = None
    if req_type:
        if to is None:
            raise JsonableError(_("Recipient required when updating type of scheduled message."))
        else:
            recipient_type_name = req_type

    if recipient_type_name is not None and recipient_type_name == "channel":
        # For now, use "stream" from Message.API_RECIPIENT_TYPES.
        # TODO: Use "channel" here, as well as in events and
        # message (created, schdeduled, drafts) objects/dicts.
        recipient_type_name = "stream"

    if recipient_type_name is not None and recipient_type_name == "stream" and topic_name is None:
        raise JsonableError(_("Topic required when updating scheduled message type to channel."))

    if recipient_type_name is not None and recipient_type_name == "direct":
        # For now, use "private" from Message.API_RECIPIENT_TYPES.
        # TODO: Use "direct" here, as well as in events and
        # scheduled message objects/dicts.
        recipient_type_name = "private"

    message_to = None
    if to is not None:
        # Because the recipient_type_name may not be updated/changed,
        # we extract these updated recipient IDs in edit_scheduled_message.
        message_to = to

    deliver_at = None
    if scheduled_delivery_timestamp is not None:
        deliver_at = timestamp_to_datetime(scheduled_delivery_timestamp)
        if deliver_at <= timezone_now():
            raise DeliveryTimeNotInFutureError

    sender = user_profile
    client = RequestNotes.get_notes(request).client
    assert client is not None

    edit_scheduled_message(
        sender,
        client,
        scheduled_message_id,
        recipient_type_name,
        message_to,
        topic_name,
        message_content,
        deliver_at,
        realm=user_profile.realm,
    )

    return json_success(request)


@typed_endpoint
def create_scheduled_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_content: Annotated[str, ApiParamConfig("content")],
    read_by_sender: Json[bool] | None = None,
    req_to: Annotated[Json[int | list[int]], ApiParamConfig("to")],
    req_type: Annotated[
        Annotated[str, check_string_in_validator(Message.API_RECIPIENT_TYPES)],
        ApiParamConfig("type"),
    ],
    scheduled_delivery_timestamp: Json[int],
    topic_name: OptionalTopic = None,
) -> HttpResponse:
    recipient_type_name = req_type
    if recipient_type_name == "direct":
        # For now, use "private" from Message.API_RECIPIENT_TYPES.
        # TODO: Use "direct" here, as well as in events and
        # scheduled message objects/dicts.
        recipient_type_name = "private"
    elif recipient_type_name == "channel":
        # For now, use "stream" from Message.API_RECIPIENT_TYPES.
        # TODO: Use "channel" here, as well as in events and
        # message (created, schdeduled, drafts) objects/dicts.
        recipient_type_name = "stream"

    deliver_at = timestamp_to_datetime(scheduled_delivery_timestamp)
    if deliver_at <= timezone_now():
        raise DeliveryTimeNotInFutureError

    sender = user_profile
    client = RequestNotes.get_notes(request).client
    assert client is not None

    if recipient_type_name == "stream":
        stream_id = extract_stream_id(req_to)
        message_to = [stream_id]
    else:
        message_to = extract_direct_message_recipient_ids(req_to)

    scheduled_message_id = check_schedule_message(
        sender,
        client,
        recipient_type_name,
        message_to,
        topic_name,
        message_content,
        deliver_at,
        realm=user_profile.realm,
        forwarder_user_profile=user_profile,
        read_by_sender=read_by_sender,
    )
    return json_success(request, data={"scheduled_message_id": scheduled_message_id})

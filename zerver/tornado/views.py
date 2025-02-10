import time
from collections.abc import Callable
from typing import Annotated, Any, TypeVar

from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import BaseModel, Json, NonNegativeInt, StringConstraints, model_validator
from typing_extensions import ParamSpec

from zerver.decorator import internal_api_view, process_client
from zerver.lib.exceptions import JsonableError
from zerver.lib.queue import get_queue_client
from zerver.lib.request import RequestNotes
from zerver.lib.response import AsynchronousResponse, json_success
from zerver.lib.sessions import narrow_request_user
from zerver.lib.typed_endpoint import ApiParamConfig, DocumentationStatus, typed_endpoint
from zerver.models import UserProfile
from zerver.models.clients import get_client
from zerver.tornado.descriptors import is_current_port
from zerver.tornado.event_queue import (
    access_client_descriptor,
    fetch_events,
    process_notification,
    send_web_reload_client_events,
)
from zerver.tornado.sharding import get_user_tornado_port, notify_tornado_queue_name

P = ParamSpec("P")
T = TypeVar("T")


def in_tornado_thread(f: Callable[P, T]) -> Callable[P, T]:
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        return f(*args, **kwargs)

    return async_to_sync(wrapped)


@internal_api_view(True)
@typed_endpoint
def notify(request: HttpRequest, *, data: Json[dict[str, Any]]) -> HttpResponse:
    # Only the puppeteer full-stack tests use this endpoint; it
    # injects an event, as if read from RabbitMQ.
    in_tornado_thread(process_notification)(data)
    return json_success(request)


@internal_api_view(True)
@typed_endpoint
def web_reload_clients(
    request: HttpRequest,
    *,
    client_count: Json[int] | None = None,
    immediate: Json[bool] = False,
) -> HttpResponse:
    sent_events = in_tornado_thread(send_web_reload_client_events)(
        immediate=immediate, count=client_count
    )
    return json_success(
        request,
        {
            "sent_events": sent_events,
            "complete": client_count is None or client_count != sent_events,
        },
    )


@typed_endpoint
def cleanup_event_queue(
    request: HttpRequest, user_profile: UserProfile, *, queue_id: str
) -> HttpResponse:
    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    log_data["extra"] = f"[{queue_id}]"

    user_port = get_user_tornado_port(user_profile)
    if not is_current_port(user_port):
        # X-Accel-Redirect is not supported for HTTP DELETE requests,
        # so we notify the shard hosting the acting user's queues via
        # enqueuing a special event.
        #
        # TODO: Because we return a 200 before confirming that the
        # event queue had been actually deleted by the process hosting
        # the queue, there's a race where a `GET /events` request can
        # succeed after getting a 200 from this endpoint.
        assert settings.USING_RABBITMQ
        get_queue_client().json_publish(
            notify_tornado_queue_name(user_port),
            {"users": [user_profile.id], "event": {"type": "cleanup_queue", "queue_id": queue_id}},
        )
        return json_success(request)

    client = access_client_descriptor(user_profile.id, queue_id)
    in_tornado_thread(client.cleanup)()
    return json_success(request)


@internal_api_view(True)
@typed_endpoint
def get_events_internal(request: HttpRequest, *, user_profile_id: Json[int]) -> HttpResponse:
    user_profile = narrow_request_user(request, user_id=user_profile_id)
    assert isinstance(user_profile, UserProfile)
    assert is_current_port(get_user_tornado_port(user_profile))

    process_client(request, user_profile, client_name="internal")
    return get_events_backend(request, user_profile)


def get_events(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    user_port = get_user_tornado_port(user_profile)
    if not is_current_port(user_port):
        # When a single realm is split across multiple Tornado shards,
        # any `GET /events` requests that are routed to the wrong
        # shard are redirected to the shard hosting the relevant
        # user's queues. We use X-Accel-Redirect for this purpose,
        # which is efficient and keeps this redirect invisible to
        # clients.
        return HttpResponse(
            "",
            headers={"X-Accel-Redirect": f"/internal/tornado/{user_port}{request.get_full_path()}"},
        )

    return get_events_backend(request, user_profile)


class UserClient(BaseModel):
    id: int
    name: Annotated[str, StringConstraints(max_length=30)]

    @model_validator(mode="before")
    @classmethod
    def convert_term(cls, elem: str) -> dict[str, Any]:
        client = get_client(elem)
        return {"id": client.id, "name": client.name}


@typed_endpoint
def get_events_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    # user_client is intended only for internal Django=>Tornado requests
    # and thus shouldn't be documented for external use.
    user_client: Annotated[
        UserClient | None,
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = None,
    last_event_id: Json[int] | None = None,
    queue_id: str | None = None,
    # apply_markdown, client_gravatar, all_public_streams, and various
    # other parameters are only used when registering a new queue via this
    # endpoint.  This is a feature used primarily by get_events_internal
    # and not expected to be used by third-party clients.
    apply_markdown: Annotated[
        Json[bool],
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = False,
    client_gravatar: Annotated[
        Json[bool],
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = False,
    slim_presence: Annotated[
        Json[bool],
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = False,
    all_public_streams: Annotated[
        Json[bool],
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = False,
    event_types: Annotated[
        Json[list[str]] | None,
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = None,
    dont_block: Json[bool] = False,
    narrow: Annotated[
        Json[list[list[str]]] | None,
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = None,
    lifespan_secs: Annotated[
        Json[NonNegativeInt],
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = 0,
    bulk_message_deletion: Annotated[
        Json[bool],
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = False,
    stream_typing_notifications: Annotated[
        Json[bool],
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = False,
    user_settings_object: Annotated[
        Json[bool],
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = False,
    pronouns_field_type_supported: Annotated[
        Json[bool],
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = True,
    linkifier_url_template: Annotated[
        Json[bool],
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = False,
    user_list_incomplete: Annotated[
        Json[bool],
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = False,
    include_deactivated_groups: Annotated[
        Json[bool],
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = False,
    archived_channels: Annotated[
        Json[bool],
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = False,
    empty_topic_name: Annotated[
        Json[bool],
        ApiParamConfig(documentation_status=DocumentationStatus.INTENTIONALLY_UNDOCUMENTED),
    ] = False,
) -> HttpResponse:
    if narrow is None:
        narrow = []
    if all_public_streams and not user_profile.can_access_public_streams():
        raise JsonableError(_("User not authorized for this query"))

    # Extract the Tornado handler from the request
    handler_id = RequestNotes.get_notes(request).tornado_handler_id
    assert handler_id is not None

    if user_client is None:
        valid_user_client = RequestNotes.get_notes(request).client
        assert valid_user_client is not None
        valid_user_client_name = valid_user_client.name
    else:
        valid_user_client_name = user_client.name

    new_queue_data = None
    if queue_id is None:
        new_queue_data = dict(
            user_profile_id=user_profile.id,
            user_recipient_id=user_profile.recipient_id,
            realm_id=user_profile.realm_id,
            event_types=event_types,
            client_type_name=valid_user_client_name,
            apply_markdown=apply_markdown,
            client_gravatar=client_gravatar,
            slim_presence=slim_presence,
            all_public_streams=all_public_streams,
            queue_timeout=lifespan_secs,
            last_connection_time=time.time(),
            narrow=narrow,
            bulk_message_deletion=bulk_message_deletion,
            stream_typing_notifications=stream_typing_notifications,
            user_settings_object=user_settings_object,
            pronouns_field_type_supported=pronouns_field_type_supported,
            linkifier_url_template=linkifier_url_template,
            user_list_incomplete=user_list_incomplete,
            include_deactivated_groups=include_deactivated_groups,
            archived_channels=archived_channels,
            empty_topic_name=empty_topic_name,
        )

    result = in_tornado_thread(fetch_events)(
        user_profile_id=user_profile.id,
        queue_id=queue_id,
        last_event_id=last_event_id,
        client_type_name=valid_user_client_name,
        dont_block=dont_block,
        handler_id=handler_id,
        new_queue_data=new_queue_data,
    )
    if "extra_log_data" in result:
        log_data = RequestNotes.get_notes(request).log_data
        assert log_data is not None
        log_data["extra"] = result["extra_log_data"]

    if result["type"] == "async":
        # Return an AsynchronousResponse; this will result in
        # Tornado discarding the response and instead long-polling the
        # request.  See zulip_finish for more design details.
        return AsynchronousResponse()
    if result["type"] == "error":
        raise result["exception"]
    return json_success(request, data=result["response"])

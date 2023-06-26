import time
from typing import Any, Callable, Mapping, Optional, Sequence, TypeVar

from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from typing_extensions import ParamSpec

from zerver.decorator import internal_notify_view, process_client
from zerver.lib.exceptions import JsonableError
from zerver.lib.queue import get_queue_client
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import AsynchronousResponse, json_success
from zerver.lib.validator import (
    check_bool,
    check_dict,
    check_int,
    check_list,
    check_string,
    to_non_negative_int,
)
from zerver.models import Client, UserProfile, get_client, get_user_profile_by_id
from zerver.tornado.descriptors import is_current_port
from zerver.tornado.event_queue import access_client_descriptor, fetch_events, process_notification
from zerver.tornado.sharding import get_user_tornado_port, notify_tornado_queue_name

P = ParamSpec("P")
T = TypeVar("T")


def in_tornado_thread(f: Callable[P, T]) -> Callable[P, T]:
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        return f(*args, **kwargs)

    return async_to_sync(wrapped)


@internal_notify_view(True)
@has_request_variables
def notify(
    request: HttpRequest, data: Mapping[str, Any] = REQ(json_validator=check_dict([]))
) -> HttpResponse:
    in_tornado_thread(process_notification)(data)
    return json_success(request)


@has_request_variables
def cleanup_event_queue(
    request: HttpRequest, user_profile: UserProfile, queue_id: str = REQ()
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


@internal_notify_view(True)
@has_request_variables
def get_events_internal(
    request: HttpRequest, user_profile_id: int = REQ(json_validator=check_int)
) -> HttpResponse:
    user_profile = get_user_profile_by_id(user_profile_id)
    RequestNotes.get_notes(request).requester_for_logs = user_profile.format_requester_for_logs()
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


@has_request_variables
def get_events_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    # user_client is intended only for internal Django=>Tornado requests
    # and thus shouldn't be documented for external use.
    user_client: Optional[Client] = REQ(
        converter=lambda var_name, s: get_client(s), default=None, intentionally_undocumented=True
    ),
    last_event_id: Optional[int] = REQ(json_validator=check_int, default=None),
    queue_id: Optional[str] = REQ(default=None),
    # apply_markdown, client_gravatar, all_public_streams, and various
    # other parameters are only used when registering a new queue via this
    # endpoint.  This is a feature used primarily by get_events_internal
    # and not expected to be used by third-party clients.
    apply_markdown: bool = REQ(
        default=False, json_validator=check_bool, intentionally_undocumented=True
    ),
    client_gravatar: bool = REQ(
        default=False, json_validator=check_bool, intentionally_undocumented=True
    ),
    slim_presence: bool = REQ(
        default=False, json_validator=check_bool, intentionally_undocumented=True
    ),
    all_public_streams: bool = REQ(
        default=False, json_validator=check_bool, intentionally_undocumented=True
    ),
    event_types: Optional[Sequence[str]] = REQ(
        default=None, json_validator=check_list(check_string), intentionally_undocumented=True
    ),
    dont_block: bool = REQ(default=False, json_validator=check_bool),
    narrow: Sequence[Sequence[str]] = REQ(
        default=[],
        json_validator=check_list(check_list(check_string)),
        intentionally_undocumented=True,
    ),
    lifespan_secs: int = REQ(
        default=0, converter=to_non_negative_int, intentionally_undocumented=True
    ),
    bulk_message_deletion: bool = REQ(
        default=False, json_validator=check_bool, intentionally_undocumented=True
    ),
    stream_typing_notifications: bool = REQ(
        default=False, json_validator=check_bool, intentionally_undocumented=True
    ),
    user_settings_object: bool = REQ(
        default=False, json_validator=check_bool, intentionally_undocumented=True
    ),
    pronouns_field_type_supported: bool = REQ(
        default=True, json_validator=check_bool, intentionally_undocumented=True
    ),
    linkifier_url_template: bool = REQ(
        default=False, json_validator=check_bool, intentionally_undocumented=True
    ),
) -> HttpResponse:
    if all_public_streams and not user_profile.can_access_public_streams():
        raise JsonableError(_("User not authorized for this query"))

    # Extract the Tornado handler from the request
    handler_id = RequestNotes.get_notes(request).tornado_handler_id
    assert handler_id is not None

    if user_client is None:
        valid_user_client = RequestNotes.get_notes(request).client
        assert valid_user_client is not None
    else:
        valid_user_client = user_client

    new_queue_data = None
    if queue_id is None:
        new_queue_data = dict(
            user_profile_id=user_profile.id,
            realm_id=user_profile.realm_id,
            event_types=event_types,
            client_type_name=valid_user_client.name,
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
        )

    result = in_tornado_thread(fetch_events)(
        user_profile_id=user_profile.id,
        queue_id=queue_id,
        last_event_id=last_event_id,
        client_type_name=valid_user_client.name,
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

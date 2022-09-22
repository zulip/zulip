import time
from typing import Callable, Optional, Sequence, TypeVar

import orjson
from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import internal_notify_view, process_client
from zerver.lib.exceptions import JsonableError
from zerver.lib.queue import get_queue_client
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import (
    check_bool,
    check_int,
    check_list,
    check_string,
    to_non_negative_int,
)
from zerver.models import Client, UserProfile, get_client, get_user_profile_by_id
from zerver.tornado.descriptors import is_current_port
from zerver.tornado.event_queue import access_client_descriptor, fetch_events, process_notification
from zerver.tornado.sharding import get_user_tornado_port, notify_tornado_queue_name

T = TypeVar("T")


def in_tornado_thread(f: Callable[[], T]) -> T:
    async def wrapped() -> T:
        return f()

    return async_to_sync(wrapped)()


@internal_notify_view(True)
def notify(request: HttpRequest) -> HttpResponse:
    in_tornado_thread(lambda: process_notification(orjson.loads(request.POST["data"])))
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
    in_tornado_thread(client.cleanup)
    return json_success(request)


@internal_notify_view(True)
@has_request_variables
def get_events_internal(
    request: HttpRequest, user_profile_id: int = REQ(json_validator=check_int)
) -> HttpResponse:
    user_profile = get_user_profile_by_id(user_profile_id)
    RequestNotes.get_notes(request).requestor_for_logs = user_profile.format_requestor_for_logs()
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
            "", headers={"X-Accel-Redirect": f"/tornado/{user_port}{request.get_full_path()}"}
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
) -> HttpResponse:
    if all_public_streams and not user_profile.can_access_public_streams():
        raise JsonableError(_("User not authorized for this query"))

    # Extract the Tornado handler from the request
    tornado_handler = RequestNotes.get_notes(request).tornado_handler
    assert tornado_handler is not None
    handler = tornado_handler()
    assert handler is not None
    handler._request = request

    if user_client is None:
        valid_user_client = RequestNotes.get_notes(request).client
        assert valid_user_client is not None
    else:
        valid_user_client = user_client

    events_query = dict(
        user_profile_id=user_profile.id,
        queue_id=queue_id,
        last_event_id=last_event_id,
        event_types=event_types,
        client_type_name=valid_user_client.name,
        all_public_streams=all_public_streams,
        lifespan_secs=lifespan_secs,
        narrow=narrow,
        dont_block=dont_block,
        handler_id=handler.handler_id,
    )

    if queue_id is None:
        events_query["new_queue_data"] = dict(
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
        )

    result = in_tornado_thread(lambda: fetch_events(events_query))
    if "extra_log_data" in result:
        log_data = RequestNotes.get_notes(request).log_data
        assert log_data is not None
        log_data["extra"] = result["extra_log_data"]

    if result["type"] == "async":
        # Mark this response with .asynchronous; this will result in
        # Tornado discarding the response and instead long-polling the
        # request.  See zulip_finish for more design details.
        response = json_success(request)
        response.asynchronous = True
        return response
    if result["type"] == "error":
        raise result["exception"]
    return json_success(request, data=result["response"])

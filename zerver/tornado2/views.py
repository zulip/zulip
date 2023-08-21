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
from .event_queue import access_client_descriptor, fetch_events, process_notification

P = ParamSpec("P")
T = TypeVar("T")


def in_tornado_thread(f: Callable[P, T]) -> Callable[P, T]:
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        return f(*args, **kwargs)

    return async_to_sync(wrapped)


@internal_notify_view(True)
@has_request_variables
def notify_presence(
    request: HttpRequest, data: Mapping[str, Any] = REQ(json_validator=check_dict([]))
) -> HttpResponse:
    in_tornado_thread(process_notification)(data)
    return json_success(request)


@internal_notify_view(True)
@has_request_variables
def get_presence_events_internal(
    request: HttpRequest, user_profile_id: int = REQ(json_validator=check_int)
) -> HttpResponse:
    user_profile = get_user_profile_by_id(user_profile_id)
    RequestNotes.get_notes(request).requester_for_logs = user_profile.format_requester_for_logs()

    process_client(request, user_profile, client_name="internal")
    return get_events_backend(request, user_profile)


def get_presence_events(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
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
    dont_block: bool = REQ(default=False, json_validator=check_bool),
    lifespan_secs: int = REQ(
        default=0, converter=to_non_negative_int, intentionally_undocumented=True
    ),
) -> HttpResponse:
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
            client_type_name=valid_user_client.name,
            queue_timeout=lifespan_secs,
            last_connection_time=time.time(),
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

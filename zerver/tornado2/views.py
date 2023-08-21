import time

from asgiref.sync import async_to_sync
from zerver.decorator import internal_notify_view, process_client
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import AsynchronousResponse, json_success
from zerver.lib.validator import check_bool, check_int, to_non_negative_int
from zerver.models import get_client, get_user_profile_by_id
from .event_queue import fetch_events

def in_tornado_thread(f):
    async def wrapped(*args, **kwargs):
        return f(*args, **kwargs)

    return async_to_sync(wrapped)


@internal_notify_view(True)
@has_request_variables
def get_presence_events_internal(
    request, user_profile_id = REQ(json_validator=check_int)
):
    user_profile = get_user_profile_by_id(user_profile_id)
    RequestNotes.get_notes(request).requester_for_logs = user_profile.format_requester_for_logs()

    process_client(request, user_profile, client_name="internal")
    return get_events_backend(request, user_profile)


def get_presence_events(request, user_profile):
    return get_events_backend(request, user_profile)


@has_request_variables
def get_events_backend(
    request,
    user_profile,
    # user_client is intended only for internal Django=>Tornado requests
    # and thus shouldn't be documented for external use.
    user_client = REQ(
        converter=lambda var_name, s: get_client(s), default=None, intentionally_undocumented=True
    ),
    last_event_id = REQ(json_validator=check_int, default=None),
    queue_id = REQ(default=None),
    dont_block = REQ(default=False, json_validator=check_bool),
    lifespan_secs = REQ(default=0, converter=to_non_negative_int, intentionally_undocumented=True),
):
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

    if result["type"] == "async":
        # Return an AsynchronousResponse; this will result in
        # Tornado discarding the response and instead long-polling the
        # request.  See zulip_finish for more design details.
        return AsynchronousResponse()

    if result["type"] == "error":
        raise result["exception"]
    return json_success(request, data=result["response"])

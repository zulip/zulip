import time
from typing import Iterable, Optional, Sequence

import orjson
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import REQ, has_request_variables, internal_notify_view, process_client
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import (
    check_bool,
    check_int,
    check_list,
    check_string,
    to_non_negative_int,
)
from zerver.models import Client, UserProfile, get_client, get_user_profile_by_id
from zerver.tornado.event_queue import fetch_events, get_client_descriptor, process_notification
from zerver.tornado.exceptions import BadEventQueueIdError
from zerver.tornado.handlers import AsyncDjangoHandler


@internal_notify_view(True)
def notify(request: HttpRequest) -> HttpResponse:
    process_notification(orjson.loads(request.POST['data']))
    return json_success()

@has_request_variables
def cleanup_event_queue(request: HttpRequest, user_profile: UserProfile,
                        queue_id: str=REQ()) -> HttpResponse:
    client = get_client_descriptor(str(queue_id))
    if client is None:
        raise BadEventQueueIdError(queue_id)
    if user_profile.id != client.user_profile_id:
        return json_error(_("You are not authorized to access this queue"))
    request._log_data['extra'] = f"[{queue_id}]"
    client.cleanup()
    return json_success()

@internal_notify_view(True)
@has_request_variables
def get_events_internal(request: HttpRequest,
                        user_profile_id: int = REQ(validator=check_int)) -> HttpResponse:
    user_profile = get_user_profile_by_id(user_profile_id)
    request._requestor_for_logs = user_profile.format_requestor_for_logs()
    process_client(request, user_profile, client_name="internal")
    return get_events_backend(request, user_profile)

def get_events(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return get_events_backend(request, user_profile)

@has_request_variables
def get_events_backend(request: HttpRequest, user_profile: UserProfile,
                       # user_client is intended only for internal Django=>Tornado requests
                       # and thus shouldn't be documented for external use.
                       user_client: Optional[Client]=REQ(converter=get_client, default=None,
                                                         intentionally_undocumented=True),
                       last_event_id: Optional[int]=REQ(converter=int, default=None),
                       queue_id: Optional[str]=REQ(default=None),
                       # apply_markdown, client_gravatar, all_public_streams, and various
                       # other parameters are only used when registering a new queue via this
                       # endpoint.  This is a feature used primarily by get_events_internal
                       # and not expected to be used by third-party clients.
                       apply_markdown: bool=REQ(default=False, validator=check_bool,
                                                intentionally_undocumented=True),
                       client_gravatar: bool=REQ(default=False, validator=check_bool,
                                                 intentionally_undocumented=True),
                       slim_presence: bool=REQ(default=False, validator=check_bool,
                                               intentionally_undocumented=True),
                       all_public_streams: bool=REQ(default=False, validator=check_bool,
                                                    intentionally_undocumented=True),
                       event_types: Optional[Sequence[str]]=REQ(default=None, validator=check_list(check_string),
                                                                intentionally_undocumented=True),
                       dont_block: bool=REQ(default=False, validator=check_bool),
                       narrow: Iterable[Sequence[str]]=REQ(default=[], validator=check_list(check_list(check_string)),
                                                           intentionally_undocumented=True),
                       lifespan_secs: int=REQ(default=0, converter=to_non_negative_int,
                                              intentionally_undocumented=True),
                       bulk_message_deletion: bool=REQ(default=False, validator=check_bool,
                                                       intentionally_undocumented=True)
                       ) -> HttpResponse:
    # Extract the Tornado handler from the request
    handler: AsyncDjangoHandler = request._tornado_handler

    if user_client is None:
        valid_user_client = request.client
    else:
        valid_user_client = user_client

    events_query = dict(
        user_profile_id = user_profile.id,
        queue_id = queue_id,
        last_event_id = last_event_id,
        event_types = event_types,
        client_type_name = valid_user_client.name,
        all_public_streams = all_public_streams,
        lifespan_secs = lifespan_secs,
        narrow = narrow,
        dont_block = dont_block,
        handler_id = handler.handler_id)

    if queue_id is None:
        events_query['new_queue_data'] = dict(
            user_profile_id = user_profile.id,
            realm_id = user_profile.realm_id,
            event_types = event_types,
            client_type_name = valid_user_client.name,
            apply_markdown = apply_markdown,
            client_gravatar = client_gravatar,
            slim_presence = slim_presence,
            all_public_streams = all_public_streams,
            queue_timeout = lifespan_secs,
            last_connection_time = time.time(),
            narrow = narrow,
            bulk_message_deletion = bulk_message_deletion)

    result = fetch_events(events_query)
    if "extra_log_data" in result:
        request._log_data['extra'] = result["extra_log_data"]

    if result["type"] == "async":
        # Mark this response with .asynchronous; this will result in
        # Tornado discarding the response and instead long-polling the
        # request.  See zulip_finish for more design details.
        handler._request = request
        response = json_success()
        response.asynchronous = True
        return response
    if result["type"] == "error":
        raise result["exception"]
    return json_success(result["response"])

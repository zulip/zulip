
import time
from typing import Iterable, List, Optional, Sequence, Text, Union

import ujson
from django.core.handlers.base import BaseHandler
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import REQ, RespondAsynchronously, \
    _RespondAsynchronously, asynchronous, \
    has_request_variables, internal_notify_view
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_bool, check_list, check_string
from zerver.models import Client, UserProfile, get_client
from zerver.tornado.event_queue import fetch_events, \
    get_client_descriptor, process_notification
from zerver.tornado.exceptions import BadEventQueueIdError

@internal_notify_view(True)
def notify(request: HttpRequest) -> HttpResponse:
    process_notification(ujson.loads(request.POST['data']))
    return json_success()

@has_request_variables
def cleanup_event_queue(request: HttpRequest, user_profile: UserProfile,
                        queue_id: Text=REQ()) -> HttpResponse:
    client = get_client_descriptor(str(queue_id))
    if client is None:
        raise BadEventQueueIdError(queue_id)
    if user_profile.id != client.user_profile_id:
        return json_error(_("You are not authorized to access this queue"))
    request._log_data['extra'] = "[%s]" % (queue_id,)
    client.cleanup()
    return json_success()

@asynchronous
@has_request_variables
def get_events_backend(request: HttpRequest, user_profile: UserProfile, handler: BaseHandler,
                       user_client: Optional[Client]=REQ(converter=get_client, default=None),
                       last_event_id: Optional[int]=REQ(converter=int, default=None),
                       queue_id: Optional[List[Text]]=REQ(default=None),
                       apply_markdown: bool=REQ(default=False, validator=check_bool),
                       client_gravatar: bool=REQ(default=False, validator=check_bool),
                       all_public_streams: bool=REQ(default=False, validator=check_bool),
                       event_types: Optional[Text]=REQ(default=None, validator=check_list(check_string)),
                       dont_block: bool=REQ(default=False, validator=check_bool),
                       narrow: Iterable[Sequence[Text]]=REQ(default=[], validator=check_list(None)),
                       lifespan_secs: int=REQ(default=0, converter=int)
                       ) -> Union[HttpResponse, _RespondAsynchronously]:
    if user_client is None:
        valid_user_client = request.client
    else:
        valid_user_client = user_client

    events_query = dict(
        user_profile_id = user_profile.id,
        user_profile_email = user_profile.email,
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
            user_profile_email = user_profile.email,
            event_types = event_types,
            client_type_name = valid_user_client.name,
            apply_markdown = apply_markdown,
            client_gravatar = client_gravatar,
            all_public_streams = all_public_streams,
            queue_timeout = lifespan_secs,
            last_connection_time = time.time(),
            narrow = narrow)

    result = fetch_events(events_query)
    if "extra_log_data" in result:
        request._log_data['extra'] = result["extra_log_data"]

    if result["type"] == "async":
        handler._request = request
        return RespondAsynchronously
    if result["type"] == "error":
        raise result["exception"]
    return json_success(result["response"])

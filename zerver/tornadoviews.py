from __future__ import absolute_import

from django.views.decorators.csrf import csrf_exempt
from zerver.models import get_client

from zerver.decorator import asynchronous, \
    authenticated_json_post_view, internal_notify_view, RespondAsynchronously, \
    has_request_variables, json_to_bool, json_to_list, REQ

from zerver.lib.response import json_success, json_error
from zerver.tornado_callbacks import process_notification

from zerver.lib.event_queue import allocate_client_descriptor, get_client_descriptor

import ujson
import logging

from zerver.lib.rest import rest_dispatch as _rest_dispatch
rest_dispatch = csrf_exempt((lambda request, *args, **kwargs: _rest_dispatch(request, globals(), *args, **kwargs)))

@internal_notify_view
def notify(request):
    process_notification(ujson.loads(request.POST['data']))
    return json_success()

@has_request_variables
def cleanup_event_queue(request, user_profile, queue_id=REQ()):
    client = get_client_descriptor(queue_id)
    if client is None:
        return json_error("Bad event queue id: %s" % (queue_id,))
    if user_profile.id != client.user_profile_id:
        return json_error("You are not authorized to access this queue")
    request._log_data['extra'] = "[%s]" % (queue_id,)
    client.cleanup()
    return json_success()

@authenticated_json_post_view
def json_get_events(request, user_profile):
    return get_events_backend(request, user_profile, apply_markdown=True)

@asynchronous
@has_request_variables
def get_events_backend(request, user_profile, handler = None,
                       user_client = REQ(converter=get_client, default=None),
                       last_event_id = REQ(converter=int, default=None),
                       queue_id = REQ(default=None),
                       apply_markdown = REQ(default=False, converter=json_to_bool),
                       all_public_streams = REQ(default=False, converter=json_to_bool),
                       event_types = REQ(default=None, converter=json_to_list),
                       dont_block = REQ(default=False, converter=json_to_bool),
                       lifespan_secs = REQ(default=0, converter=int)):
    if user_client is None:
        user_client = request.client

    orig_queue_id = queue_id
    if queue_id is None:
        if dont_block:
            client = allocate_client_descriptor(user_profile.id, user_profile.realm.id,
                                                event_types, user_client, apply_markdown,
                                                all_public_streams, lifespan_secs)
            queue_id = client.event_queue.id
        else:
            return json_error("Missing 'queue_id' argument")
    else:
        if last_event_id is None:
            return json_error("Missing 'last_event_id' argument")
        client = get_client_descriptor(queue_id)
        if client is None:
            return json_error("Bad event queue id: %s" % (queue_id,))
        if user_profile.id != client.user_profile_id:
            return json_error("You are not authorized to get events from this queue")
        client.event_queue.prune(last_event_id)
        client.disconnect_handler()

    if not client.event_queue.empty() or dont_block:
        ret = {'events': client.event_queue.contents()}
        if orig_queue_id is None:
            ret['queue_id'] = queue_id
        request._log_data['extra'] = "[%s/%s]" % (queue_id, len(ret["events"]))
        return json_success(ret)

    handler._request = request
    client.connect_handler(handler)

    # runtornado recognizes this special return value.
    return RespondAsynchronously

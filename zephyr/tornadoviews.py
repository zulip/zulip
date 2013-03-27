from django.conf import settings
from zephyr.models import UserActivity

from zephyr.decorator import asynchronous, authenticated_api_view, \
    authenticated_json_post_view, internal_notify_view, RespondAsynchronously, \
    has_request_variables, POST, to_non_negative_int, json_to_bool, json_to_list, \
    JsonableError, authenticated_rest_api_view, REQ

from zephyr.lib.response import json_response, json_success, json_error

from zephyr.tornado_callbacks import \
    get_user_pointer, fetch_stream_messages, fetch_user_messages, \
    add_stream_receive_callback, add_user_receive_callback, \
    add_pointer_update_callback, process_notification

from zephyr.lib.cache_helpers import cache_get_message
from zephyr.lib.event_queue import allocate_client_descriptor, get_client_descriptor

import datetime
import simplejson
import socket
import time
import sys
import logging

@internal_notify_view
def notify(request):
    process_notification(simplejson.loads(request.POST['data']))
    return json_success()

@asynchronous
@authenticated_json_post_view
def json_get_updates(request, user_profile, handler):
    client_id = request.session.session_key
    return get_updates_backend(request, user_profile, handler, client_id,
                               client=request.client, apply_markdown=True)

@asynchronous
@authenticated_api_view
def api_get_messages(request, user_profile, handler):
    return get_messages_backend(request, user_profile, handler)

@has_request_variables
def get_messages_backend(request, user_profile, handler, client_id=REQ(default=None),
                     apply_markdown=REQ(default=False, converter=json_to_bool)):
    return get_updates_backend(request, user_profile, handler, client_id,
                               apply_markdown=apply_markdown,
                               client=request.client)

@asynchronous
@authenticated_rest_api_view
def rest_get_messages(request, user_profile, handler):
    return get_messages_backend(request, user_profile, handler)

def format_updates_response(messages=[], apply_markdown=True,
                            user_profile=None, new_pointer=None,
                            client=None, update_types=[],
                            client_server_generation=None):
    if client is not None and client.name.endswith("_mirror"):
        messages = [m for m in messages if m.sending_client.name != client.name]
    ret = {'messages': [message.to_dict(apply_markdown) for message in messages],
           "result": "success",
           "msg": "",
           'update_types': update_types}
    if client_server_generation is not None:
        ret['server_generation'] = settings.SERVER_GENERATION
    if new_pointer is not None:
        ret['new_pointer'] = new_pointer

    return ret

def return_messages_immediately(user_profile, client_id, last,
                                client_server_generation,
                                client_pointer, dont_block,
                                stream_name, **kwargs):
    update_types = []
    new_pointer = None
    if dont_block:
        update_types.append("nonblocking_request")

    if (client_server_generation is not None and
        client_server_generation != settings.SERVER_GENERATION):
        update_types.append("client_reload")

    ptr = get_user_pointer(user_profile.id)
    if (client_pointer is not None and ptr > client_pointer):
        new_pointer = ptr
        update_types.append("pointer_update")

    if last is not None:
        if stream_name is not None:
            message_ids = fetch_stream_messages(user_profile.realm.id, stream_name, last)
        else:
            message_ids = fetch_user_messages(user_profile.id, last)
        messages = map(cache_get_message, message_ids)

        # Filter for mirroring before checking whether there are any
        # messages to pass on.  If we don't do this, when the only message
        # to forward is one that was sent via the mirroring, the API
        # client will end up in an endless loop requesting more data from
        # us.
        if "client" in kwargs and kwargs["client"].name.endswith("_mirror"):
            messages = [m for m in messages if
                        m.sending_client.name != kwargs["client"].name]
    else: # last is None, so we're not interested in any old messages
        messages = []

    if messages:
        update_types.append("new_messages")

    if update_types:
        return format_updates_response(messages=messages,
                                       user_profile=user_profile,
                                       new_pointer=new_pointer,
                                       client_server_generation=client_server_generation,
                                       update_types=update_types,
                                       **kwargs)

    return None

# Note: We allow any stream name at all here! Validation and
# authorization (is the stream "public") are handled by the caller of
# notify new_message. If a user makes a get_updates request for a
# nonexistent or non-public stream, they won't get an error -- they'll
# just never receive any messages.
@has_request_variables
def get_updates_backend(request, user_profile, handler, client_id,
                        last = REQ(converter=to_non_negative_int, default=None),
                        client_server_generation = REQ(whence='server_generation', default=None,
                                                        converter=int),
                        client_pointer = REQ(whence='pointer', converter=int, default=None),
                        dont_block = REQ(converter=json_to_bool, default=False),
                        stream_name = REQ(default=None), apply_markdown=True,
                        **kwargs):
    resp = return_messages_immediately(user_profile, client_id, last,
                                       client_server_generation,
                                       client_pointer,
                                       dont_block, stream_name,
                                       apply_markdown=apply_markdown, **kwargs)
    if resp is not None:
        handler.humbug_finish(resp, request, apply_markdown)

        # We have already invoked handler.humbug_finish(), so we bypass the usual view
        # response path.  We are "responding asynchronously" except that it
        # already happened.  This is slightly weird.
        return RespondAsynchronously

    # Enter long-polling mode.
    #
    # Instead of responding to the client right away, leave our connection open
    # and return to the Tornado main loop.  One of the notify_* views will
    # eventually invoke one of these callbacks, which will send the delayed
    # response.

    def cb(**cb_kwargs):
        request._time_restarted = time.time()
        if handler.request.connection.stream.closed():
            return
        try:
            # It would be nice to be able to do these checks in
            # UserProfile.receive, but it doesn't know what the value
            # of "last" was for each callback.
            if last is not None and "messages" in cb_kwargs:
                messages = cb_kwargs["messages"]

                # Make sure the client doesn't get a message twice
                # when messages are processed out of order.
                if messages[0].id <= last:
                    # We must return a response because we don't have
                    # a way to re-queue a callback and so the client
                    # must do it by making a new request
                    handler.humbug_finish({"result": "success",
                                           "msg": "",
                                           'update_types': []},
                                          request, apply_markdown)
                    return

            kwargs.update(cb_kwargs)
            res = format_updates_response(user_profile=user_profile,
                                          client_server_generation=client_server_generation,
                                          apply_markdown=apply_markdown,
                                          **kwargs)
            handler.humbug_finish(res, request, apply_markdown)
        except socket.error:
            pass

    if stream_name is not None:
        add_stream_receive_callback(user_profile.realm.id, stream_name, handler.async_callback(cb))
    else:
        add_user_receive_callback(user_profile, handler.async_callback(cb))
    if client_pointer is not None:
        add_pointer_update_callback(user_profile, handler.async_callback(cb))

    # runtornado recognizes this special return value.
    return RespondAsynchronously

@asynchronous
@authenticated_json_post_view
def json_get_events(request, user_profile, handler):
    return get_events_backend(request, user_profile, handler)

@asynchronous
@authenticated_rest_api_view
@has_request_variables
def rest_get_events(request, user_profile, handler,
                    apply_markdown=REQ(default=False, converter=json_to_bool)):
    return get_events_backend(request, user_profile, handler,
                              apply_markdown=apply_markdown)

@has_request_variables
def get_events_backend(request, user_profile, handler,
                       last_event_id = REQ(converter=int, default=None),
                       queue_id = REQ(default=None), apply_markdown=True,
                       event_types = REQ(default=None, converter=json_to_list),
                       dont_block = REQ(default=False, converter=json_to_bool)):
    if queue_id is None:
        if dont_block:
            client = allocate_client_descriptor(user_profile.id, event_types,
                                                apply_markdown)
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
        return json_success({'events': client.event_queue.contents(),
                             'queue_id': queue_id})

    handler._request = request
    client.connect_handler(handler)

    # runtornado recognizes this special return value.
    return RespondAsynchronously

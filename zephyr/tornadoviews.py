from django.conf import settings
from zephyr.models import Message, UserProfile, UserMessage, UserActivity, Recipient, Stream

from zephyr.decorator import asynchronous, authenticated_api_view, \
    authenticated_json_post_view, internal_notify_view, RespondAsynchronously, \
    has_request_variables, POST, json_to_list, to_non_negative_int, \
    JsonableError
from zephyr.lib.response import json_success, json_error

import os
import datetime
import simplejson
import socket
import time
import collections
import sys
import logging
import subprocess
from django.core.cache import cache
from zephyr.lib.cache import cache_with_key
from zephyr.lib.message_cache import cache_save_message, cache_get_message

SERVER_GENERATION = int(time.time())

class Callbacks(object):
    # A user received a message. The key is user_profile.id.
    TYPE_USER_RECEIVE = 0

    # A stream received a message. The key is a tuple
    #   (realm_id, lowercased stream name).
    # See comment attached to the global stream_messages for why.
    # Callers of this callback need to be careful to provide
    # a lowercased stream name.
    TYPE_STREAM_RECEIVE = 1

    # A user's pointer was updated. The key is user_profile.id.
    TYPE_POINTER_UPDATE = 2

    TYPE_MAX = 3

    def __init__(self):
        self.table = {}

    def add(self, key, cb_type, callback):
        if not self.table.has_key(key):
            self.create_key(key)
        self.table[key][cb_type].append(callback)

    def call(self, key, cb_type, **kwargs):
        if not self.table.has_key(key):
            self.create_key(key)

        for cb in self.table[key][cb_type]:
            cb(**kwargs)

        self.table[key][cb_type] = []

    def create_key(self, key):
        self.table[key] = [[] for i in range(0, Callbacks.TYPE_MAX)]

callbacks_table = Callbacks()

def add_user_receive_callback(user_profile, cb):
    callbacks_table.add(user_profile.id, Callbacks.TYPE_USER_RECEIVE, cb)

def add_stream_receive_callback(realm_id, stream_name, cb):
    callbacks_table.add((realm_id, stream_name.lower()), Callbacks.TYPE_STREAM_RECEIVE, cb)

def add_pointer_update_callback(user_profile, cb):
    callbacks_table.add(user_profile.id, Callbacks.TYPE_POINTER_UPDATE, cb)

# in-process caching mechanism for tracking usermessages
#
# user_messages:   Map user_profile_id => [deque of message ids he received]
#
# We don't use all the features of a deque -- the important ones are:
# * O(1) insert of new highest message id
# * O(k) read of highest k message ids
# * Automatic maximum size support.
user_messages = {}

# Same deal as user_messages, but for streams.
#
# stream_messages: Map (realm_id, lowercased stream name) => [deque of message ids it received]
#
# Why don't we index by the stream_id? Because the client will make a
# request that specifies a particular realm and stream name, and since
# we're running within tornado, we don't want to have to do a database
# lookup to find the matching entry in this table.
stream_messages = {}
USERMESSAGE_CACHE_COUNT = 50000
STREAMMESSAGE_CACHE_COUNT = 5000
cache_minimum_id = sys.maxint
def initialize_user_messages():
    global cache_minimum_id
    try:
        cache_minimum_id = Message.objects.all().order_by("-id")[0].id - USERMESSAGE_CACHE_COUNT
    except Message.DoesNotExist:
        cache_minimum_id = 1

    for um in UserMessage.objects.filter(message_id__gte=cache_minimum_id).order_by("message"):
        add_user_message(um.user_profile_id, um.message_id)

    streams = {}
    for stream in Stream.objects.select_related().all():
        streams[stream.id] = stream
    for m in (Message.objects.only("id", "recipient").select_related("recipient")
              .filter(id__gte=cache_minimum_id + (USERMESSAGE_CACHE_COUNT - STREAMMESSAGE_CACHE_COUNT),
                      recipient__type=Recipient.STREAM).order_by("id")):
        stream = streams[m.recipient.type_id]
        add_stream_message(stream.realm.id, stream.name, m.id)

    # Filling the memcached cache is a little slow, so do it in a child process.
    subprocess.Popen(["python", os.path.join(os.path.dirname(__file__), "..", "manage.py"),
                      "fill_message_cache"])

def add_user_message(user_profile_id, message_id):
    add_table_message(user_messages, user_profile_id, message_id)

def add_stream_message(realm_id, stream_name, message_id):
    add_table_message(stream_messages, (realm_id, stream_name.lower()), message_id)

def add_table_message(table, key, message_id):
    if cache_minimum_id == sys.maxint:
        initialize_user_messages()
    table.setdefault(key, collections.deque(maxlen=400))
    table[key].appendleft(message_id)

def fetch_user_messages(user_profile_id, last):
    return fetch_table_messages(user_messages, user_profile_id, last)

def fetch_stream_messages(realm_id, stream_name, last):
    return fetch_table_messages(stream_messages, (realm_id, stream_name.lower()), last)

def fetch_table_messages(table, key, last):
    if cache_minimum_id == sys.maxint:
        initialize_user_messages()

    # We need to do this check after initialize_user_messages has been called.
    if last < cache_minimum_id:
        # The user's client has a way-too-old value for 'last', we
        # should return an error
        raise JsonableError("last value of %d too old!  Minimum valid is %d!" %
                            (last, cache_minimum_id))

    # We need to initialize the deque here for any new users or
    # streams that were created since Tornado was started
    table.setdefault(key, collections.deque(maxlen=400))

    message_list = []
    for message_id in table[key]:
        if message_id <= last:
            return reversed(message_list)
        message_list.append(message_id)
    return []

# The user receives this message
def user_receive_message(user_profile_id, message):
    add_user_message(user_profile_id, message.id)
    callbacks_table.call(user_profile_id, Callbacks.TYPE_USER_RECEIVE,
                         messages=[message], update_types=["new_messages"])

# The stream receives this message
def stream_receive_message(realm_id, stream_name, message):
    add_stream_message(realm_id, stream_name, message.id)
    callbacks_table.call((realm_id, stream_name.lower()),
                         Callbacks.TYPE_STREAM_RECEIVE,
                         messages=[message], update_types=["new_messages"])

# Simple caching implementation module for user pointers
#
# TODO: Write something generic in cache.py to support this
# functionality?  The current primitives there don't support storing
# to the cache.
user_pointers = {}
def get_user_pointer(user_profile_id):
    if user_pointers == {}:
        # Once, on startup, fill in the user_pointers table with
        # everyone's current pointers
        for u in UserProfile.objects.all():
            user_pointers[u.id] = u.pointer
    if user_profile_id not in user_pointers:
        # This is a new user created since Tornado was started, so
        # they will have an initial pointer of -1.
        return -1
    return user_pointers[user_profile_id]

def set_user_pointer(user_profile_id, pointer):
    user_pointers[user_profile_id] = pointer

def update_pointer(user_profile_id, new_pointer, pointer_updater):
    set_user_pointer(user_profile_id, new_pointer)
    callbacks_table.call(user_profile_id, Callbacks.TYPE_POINTER_UPDATE,
                         new_pointer=new_pointer,
                         update_types=["pointer_update"])

@internal_notify_view
def notify_new_message(request):
    recipient_profile_ids = map(int, json_to_list(request.POST['users']))
    message = cache_get_message(int(request.POST['message']))

    for user_profile_id in recipient_profile_ids:
        user_receive_message(user_profile_id, message)

    if 'stream_name' in request.POST:
        realm_id = int(request.POST['realm_id'])
        stream_name = request.POST['stream_name']
        stream_receive_message(realm_id, stream_name, message)

    return json_success()

@internal_notify_view
def notify_pointer_update(request):
    user_profile_id = int(request.POST['user'])
    new_pointer = int(request.POST['new_pointer'])
    pointer_updater = request.POST['pointer_updater']

    update_pointer(user_profile_id, new_pointer, pointer_updater)

    return json_success()

@asynchronous
@authenticated_json_post_view
def json_get_updates(request, user_profile, handler):
    client_id = request.session.session_key
    return get_updates_backend(request, user_profile, handler, client_id,
                               client=request._client, apply_markdown=True)

@asynchronous
@authenticated_api_view
@has_request_variables
def api_get_messages(request, user_profile, handler, client_id=POST(default=None),
                     apply_markdown=POST(default=False, converter=simplejson.loads)):
    return get_updates_backend(request, user_profile, handler, client_id,
                               apply_markdown=apply_markdown,
                               client=request._client)

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
        ret['server_generation'] = SERVER_GENERATION
    if new_pointer is not None:
        ret['new_pointer'] = new_pointer
    if user_profile.realm.domain == "mit.edu":
        try:
            activity = UserActivity.objects.get(user_profile = user_profile,
                                                query="/api/v1/get_messages",
                                                client__name="zephyr_mirror")
            ret['zephyr_mirror_active'] = \
                (activity.last_visit.replace(tzinfo=None) >
                 datetime.datetime.utcnow() - datetime.timedelta(minutes=5))
        except UserActivity.DoesNotExist:
            ret['zephyr_mirror_active'] = False

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
        client_server_generation != SERVER_GENERATION):
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

def send_with_safety_check(response, handler, apply_markdown=True, **kwargs):
    # Make sure that Markdown rendering really happened, if requested.
    # This is a security issue because it's where we escape HTML.
    # c.f. ticket #64
    #
    # apply_markdown=True is the fail-safe default.
    if response['result'] == 'success' and apply_markdown:
        for msg in response['messages']:
            if msg['content_type'] != 'text/html':
                handler.set_status(500)
                handler.finish('Internal error: bad message format')
                return
    if response['result'] == 'error':
        handler.set_status(400)
    handler.finish(response)

# Note: We allow any stream name at all here! Validation and
# authorization (is the stream "public") are handled by the caller of
# notify_new_message. If a user makes a get_updates request for a
# nonexistent or non-public stream, they won't get an error -- they'll
# just never receive any messages.
@has_request_variables
def get_updates_backend(request, user_profile, handler, client_id,
                        last = POST(converter=to_non_negative_int, default=None),
                        client_server_generation = POST(whence='server_generation', default=None,
                                                        converter=int),
                        client_pointer = POST(whence='pointer', converter=int, default=None),
                        dont_block = POST(converter=simplejson.loads, default=False),
                        stream_name = POST(default=None),
                        **kwargs):
    resp = return_messages_immediately(user_profile, client_id, last,
                                       client_server_generation,
                                       client_pointer,
                                       dont_block, stream_name, **kwargs)
    if resp is not None:
        send_with_safety_check(resp, handler, **kwargs)

        # We have already invoked handler.finish(), so we bypass the usual view
        # response path.  We are "responding asynchronously" except that it
        # already happened.  This is slightly weird, but lets us share
        # send_with_safety_check with the code below.
        return RespondAsynchronously

    # Enter long-polling mode.
    #
    # Instead of responding to the client right away, leave our connection open
    # and return to the Tornado main loop.  One of the notify_* views will
    # eventually invoke one of these callbacks, which will send the delayed
    # response.

    def cb(**cb_kwargs):
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
                    handler.finish({"result": "success",
                                    "msg": "",
                                    'update_types': []})
                    return

            kwargs.update(cb_kwargs)
            res = format_updates_response(user_profile=user_profile,
                                          client_server_generation=client_server_generation,
                                          **kwargs)
            send_with_safety_check(res, handler, **kwargs)
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

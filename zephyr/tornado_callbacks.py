from django.conf import settings
from zephyr.models import Message, UserProfile, UserMessage, \
    Recipient, Stream, get_stream

from zephyr.decorator import JsonableError
from zephyr.lib.cache_helpers import cache_get_message

import os
import sys
import logging
import requests
import simplejson
import subprocess
import collections

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
# user table:   Map user_profile_id => [deque of message ids he received]
#
# We don't use all the features of a deque -- the important ones are:
# * O(1) insert of new highest message id
# * O(k) read of highest k message ids
# * Automatic maximum size support.
#
# stream table: Map (realm_id, lowercased stream name) => [deque of message ids it received]
#
# Why don't we index by the stream_id? Because the client will make a
# request that specifies a particular realm and stream name, and since
# we're running within tornado, we don't want to have to do a database
# lookup to find the matching entry in this table.

mtables = {
    'user': {},
    'stream': {},
}

USERMESSAGE_CACHE_COUNT = 25000
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

    if not settings.DEPLOYED:
        # Filling the memcached cache is a little slow, so do it in a child process.
        # For DEPLOYED cases, we run this from restart_server.
        subprocess.Popen(["python", os.path.join(os.path.dirname(__file__), "..", "manage.py"),
                          "fill_memcached_caches"])

def add_user_message(user_profile_id, message_id):
    add_table_message("user", user_profile_id, message_id)

def add_stream_message(realm_id, stream_name, message_id):
    add_table_message("stream", (realm_id, stream_name.lower()), message_id)

def add_table_message(table, key, message_id):
    if cache_minimum_id == sys.maxint:
        initialize_user_messages()
    mtables[table].setdefault(key, collections.deque(maxlen=400))
    mtables[table][key].appendleft(message_id)

def fetch_user_messages(user_profile_id, last):
    return fetch_table_messages("user", user_profile_id, last)

def fetch_stream_messages(realm_id, stream_name, last):
    return fetch_table_messages("stream", (realm_id, stream_name.lower()), last)

def fetch_table_messages(table, key, last):
    if cache_minimum_id == sys.maxint:
        initialize_user_messages()

    # We need to initialize the deque here for any new users or
    # streams that were created since Tornado was started
    mtables[table].setdefault(key, collections.deque(maxlen=400))

    # We need to do this check after initialize_user_messages has been called.
    if len(mtables[table][key]) == 0:
        # Since the request contains a value of "last", we can assume
        # that the relevant user or stream has actually received a
        # message, which means that mtabes[table][key] will not remain
        # empty after the below completes.
        #
        # Thus, we will run this code at most once per key (user or
        # stream that is being lurked on).  Further, we only do this
        # query for those keys that have not received a message since
        # cache_minimum_id.  So we can afford to do a database query
        # from Tornado in this case.
        if table == "user":
            logging.info("tornado: Doing database query for user %d" % (key,),)
            for um in reversed(UserMessage.objects.filter(user_profile_id=key).order_by('-message')[:400]):
                add_user_message(um.user_profile_id, um.message_id)
        elif table == "stream":
            logging.info("tornado: Doing database query for stream %s" % (key,))
            (realm_id, stream_name) = key
            stream = get_stream(stream_name, realm_id)
            # If a buggy client submits a "last" value with a nonexistent stream,
            # do nothing (and proceed to longpoll) rather than crashing.
            if stream is not None:
                recipient = Recipient.objects.get(type=Recipient.STREAM, type_id=stream.id)
                for m in Message.objects.only("id", "recipient").filter(recipient=recipient).order_by("id")[:400]:
                    add_stream_message(realm_id, stream_name, m.id)

    if len(mtables[table][key]) == 0:
        # Check the our assumption above that there are messages here.
        # If false, this may just mean a misbehaving client submitted
        # "last" even though it has no messages (in which case we
        # should proceed with longpolling by falling through).  But it
        # could also be a server bug, so we log a warning.
        logging.warning("Unexpected empty message queue for key %s!" % (key,))
    elif last < mtables[table][key][-1]:
        # The user's client has a way-too-old value for 'last'
        # (presumably 400 messages old), we should return an error

        # The error handler for get_updates in zephyr.js parses this
        # message. If you change this message, you must update that
        # error handler.
        raise JsonableError("last value of %d too old!  Minimum valid is %d!" %
                            (last, mtables[table][key][-1]))

    message_list = []
    for message_id in mtables[table][key]:
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

def update_pointer(user_profile_id, new_pointer):
    set_user_pointer(user_profile_id, new_pointer)
    callbacks_table.call(user_profile_id, Callbacks.TYPE_POINTER_UPDATE,
                         new_pointer=new_pointer,
                         update_types=["pointer_update"])

def process_new_message(data):
    message = cache_get_message(data['message'])

    for user_profile_id in data['users']:
        user_receive_message(user_profile_id, message)

    if 'stream_name' in data:
        stream_receive_message(data['realm_id'], data['stream_name'], message)

def process_notification(data):
    if data['type'] == 'new_message':
        process_new_message(data)
    elif data['type'] == 'pointer_update':
        update_pointer(data['user'], data['new_pointer'])
    else:
        raise JsonableError('bad notification type ' + data['type'])

# Runs in the Django process to send a notification to Tornado.
#
# We use JSON rather than bare form parameters, so that we can represent
# different types and for compatibility with non-HTTP transports.
def send_notification(data):
    requests.post(settings.TORNADO_SERVER + '/notify_tornado', data=dict(
        data   = simplejson.dumps(data),
        secret = settings.SHARED_SECRET))

from __future__ import absolute_import

from django.conf import settings
from django.utils.timezone import now

from zerver.models import Message, UserProfile, UserMessage, \
    Recipient, Stream, get_stream, get_user_profile_by_id

from zerver.decorator import JsonableError
from zerver.lib.cache import cache_get_many, message_cache_key, \
    user_profile_by_id_cache_key, cache_save_user_profile
from zerver.lib.cache_helpers import cache_save_message
from zerver.lib.queue import queue_json_publish
from zerver.lib.event_queue import get_client_descriptors_for_user,\
    get_client_descriptors_for_realm_all_streams
from zerver.lib.timestamp import timestamp_to_datetime

import os
import sys
import time
import logging
import requests
import ujson
import subprocess
import collections
import datetime
from django.db import connection

# Send email notifications to idle users
# after they are idle for 1 hour
NOTIFY_AFTER_IDLE_HOURS = 1

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

    # These next few lines implement the following Django ORM
    # algorithm using raw SQL:
    ## for um in UserMessage.objects.filter(message_id__gte=cache_minimum_id).order_by("message"):
    ##     add_user_message(um.user_profile_id, um.message_id)
    # We do this because marshalling the Django objects is very
    # inefficient; total time consumed with the raw SQL is about
    # 600ms, vs. 3000ms-5000ms if we go through the ORM.
    cursor = connection.cursor()
    cursor.execute("SELECT user_profile_id, message_id from zerver_usermessage " +
                   "where message_id >= %s order by message_id", [cache_minimum_id])
    for row in cursor.fetchall():
        (user_profile_id, message_id) = row
        add_user_message(user_profile_id, message_id)

    streams = {}
    for stream in Stream.objects.select_related().all():
        streams[stream.id] = stream
    for m in (Message.objects.only("id", "recipient").select_related("recipient")
              .filter(id__gte=cache_minimum_id + (USERMESSAGE_CACHE_COUNT - STREAMMESSAGE_CACHE_COUNT),
                      recipient__type=Recipient.STREAM).order_by("id")):
        stream = streams[m.recipient.type_id]
        add_stream_message(stream.realm.id, stream.name, m.id)

    if not settings.DEPLOYED and not settings.TEST_SUITE:
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

        # The error handler for get_updates in zulip.js parses this
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

    event = dict(type='pointer', pointer=new_pointer)
    for client in get_client_descriptors_for_user(user_profile_id):
        if client.accepts_event_type(event['type']):
            client.add_event(event.copy())


def receives_offline_notifications(user_profile):
    return (user_profile.enable_offline_email_notifications and
            not user_profile.is_bot)

def receives_offline_notifications_by_id(user_profile_id):
    user_profile = get_user_profile_by_id(user_profile_id)
    return receives_offline_notifications(user_profile)

def build_offline_notification_event(user_profile_id, message_id):
    return {"user_profile_id": user_profile_id,
            "message_id": message_id,
            "timestamp": time.time()}

def missedmessage_hook(user_profile_id, queue, last_for_client):
    # Only process missedmessage hook when the last queue for a
    # client has been garbage collected
    if not last_for_client:
        return

    # If a user has gone offline but has unread messages
    # received in the idle time, send them a missed
    # message email
    if not receives_offline_notifications_by_id(user_profile_id):
        return

    message_ids = []
    for event in queue.event_queue.contents():
        if not event['type'] == 'message' or not event['flags']:
            continue

        if 'mentioned' in event['flags'] and not 'read' in event['flags']:
            message_ids.append(event['message']['id'])

    for msg_id in message_ids:
        event = build_offline_notification_event(user_profile_id, msg_id)
        queue_json_publish("missedmessage_emails", event, lambda event: None)

def cache_load_message_data(message_id, users):
    # Get everything that we'll need out of memcached in one fetch, to save round-trip times:
    # * The message itself
    # * Every recipient's UserProfile
    user_profile_keys = [user_profile_by_id_cache_key(user_data['id']) for user_data in users]

    cache_keys = [message_cache_key(message_id)]
    cache_keys.extend(user_profile_keys)

    # Single memcached fetch
    result = cache_get_many(cache_keys)

    cache_extractor = lambda result: result[0] if result is not None else None

    message = cache_extractor(result.get(cache_keys[0], None))

    user_profiles = dict((user_data['id'], cache_extractor(result.get(user_profile_by_id_cache_key(user_data['id']), None)))
                            for user_data in users)

    # Any data that was not found in memcached, we have to load from the database
    # and save back. This should never happen---we take steps to keep recent messages,
    # all user profile & presence objects in memcached.
    if message is None:
        if not settings.TEST_SUITE:
            logging.warning("Tornado failed to load message from memcached when delivering!")

        message = Message.objects.select_related().get(id=message_id)
        cache_save_message(message)

    for user_profile_id, user_profile in user_profiles.iteritems():
        if user_profile:
            continue
        if not settings.TEST_SUITE:
            logging.warning("Tornado failed to load user profile from memcached when delivering message!")

        user_profile = UserProfile.objects.select_related().get(id=user_profile_id)
        user_profiles[user_profile_id] = user_profile
        cache_save_user_profile(user_profile)

    return message, user_profiles

def receiver_is_idle(user_profile, realm_presences):
    # If a user has no message-receiving event queues, they've got no open zulip
    # session so we notify them
    all_client_descriptors = get_client_descriptors_for_user(user_profile.id)
    message_event_queues = [client for client in all_client_descriptors if client.accepts_event_type('message')]
    off_zulip = len(message_event_queues) == 0

    # It's possible a recipient is not in the realm of a sender. We don't have
    # presence information in this case (and it's hard to get without an additional
    # db query) so we simply don't try to guess if this cross-realm recipient
    # has been idle for too long
    if realm_presences is None or not user_profile.email in realm_presences:
        return off_zulip

    # If the most recent online status from a user is >1hr in the past, we notify
    # them regardless of whether or not they have an open window
    user_presence = realm_presences[user_profile.email]
    idle_too_long = False
    newest = None
    for client, status in user_presence.iteritems():
        if newest is None or status['timestamp'] > newest['timestamp']:
            newest = status

    update_time = timestamp_to_datetime(newest['timestamp'])
    if now() - update_time > datetime.timedelta(hours=NOTIFY_AFTER_IDLE_HOURS):
        idle_too_long = True

    return off_zulip or idle_too_long

def process_new_message(data):
    message, user_profiles = cache_load_message_data(data['message'],
                                                     data['users'])

    realm_presences = data['presences']

    message_dict_markdown = message.to_dict(True)
    message_dict_no_markdown = message.to_dict(False)

    # To remove duplicate clients: Maps queue ID to (Client, flags)
    send_to_clients = dict()

    if 'stream_name' in data and not data.get("invite_only"):
        for client in get_client_descriptors_for_realm_all_streams(data['realm_id']):
            send_to_clients[client.event_queue.id] = (client, None)

    for user_data in data['users']:
        user_profile_id = user_data['id']
        user_profile = user_profiles[user_data['id']]
        flags = user_data.get('flags', [])

        user_receive_message(user_profile_id, message)

        for client in get_client_descriptors_for_user(user_profile_id):
            send_to_clients[client.event_queue.id] = (client, flags)

        # If the recipient was offline and the message was a single or group PM to him
        # or she was @-notified potentially notify more immediately
        received_pm = message.recipient.type in (Recipient.PERSONAL, Recipient.HUDDLE) and \
                        user_profile_id != message.sender.id
        mentioned = 'mentioned' in flags

        if (received_pm or mentioned) and receiver_is_idle(user_profile, realm_presences):
            if receives_offline_notifications(user_profile):
                event = build_offline_notification_event(user_profile_id, message.id)

                # We require RabbitMQ to do this, as we can't call the email handler
                # from the Tornado process. So if there's no rabbitmq support do nothing
                queue_json_publish("missedmessage_emails", event, lambda event: None)

    for client, flags in send_to_clients.itervalues():
        if not client.accepts_event_type('message'):
            continue

        # The below prevents (Zephyr) mirroring loops.
        if ('mirror' in message.sending_client.name and
            message.sending_client == client.client_type):
            continue

        if client.apply_markdown:
            message_dict = message_dict_markdown
        else:
            message_dict = message_dict_no_markdown

        # Make sure Zephyr mirroring bots know whether stream is invite-only
        if "mirror" in client.client_type.name and data.get("invite_only"):
            message_dict = message_dict.copy()
            message_dict["invite_only_stream"] = True

        event = dict(type='message', message=message_dict, flags=flags)
        client.add_event(event)

    if 'stream_name' in data:
        stream_receive_message(data['realm_id'], data['stream_name'], message)

def process_event(data):
    event = data['event']
    for user_profile_id in data['users']:
        for client in get_client_descriptors_for_user(user_profile_id):
            if client.accepts_event_type(event['type']):
                client.add_event(event.copy())

def process_notification(data):
    if 'type' not in data:
        # Generic event that doesn't need special handling
        process_event(data)
    elif data['type'] == 'new_message':
        process_new_message(data)
    elif data['type'] == 'pointer_update':
        update_pointer(data['user'], data['new_pointer'])
    else:
        raise JsonableError('bad notification type ' + data['type'])

# Runs in the Django process to send a notification to Tornado.
#
# We use JSON rather than bare form parameters, so that we can represent
# different types and for compatibility with non-HTTP transports.

def send_notification_http(data):
    if settings.TORNADO_SERVER and not settings.RUNNING_INSIDE_TORNADO:
        requests.post(settings.TORNADO_SERVER + '/notify_tornado', data=dict(
                data   = ujson.dumps(data),
                secret = settings.SHARED_SECRET))
    else:
        process_notification(data)

def send_notification(data):
    return queue_json_publish("notify_tornado", data, send_notification_http)

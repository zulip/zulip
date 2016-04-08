from __future__ import absolute_import
from typing import Any

# This file needs to be different from cache.py because cache.py
# cannot import anything from zerver.models or we'd have an import
# loop
from django.conf import settings
from zerver.models import Message, UserProfile, Stream, get_stream_cache_key, \
    Recipient, get_recipient_cache_key, Client, get_client_cache_key, \
    Huddle, huddle_hash_cache_key
from zerver.lib.cache import cache_with_key, cache_set, message_cache_key, \
    user_profile_by_email_cache_key, user_profile_by_id_cache_key, \
    get_remote_cache_time, get_remote_cache_requests, cache_set_many
from django.utils.importlib import import_module
from django.contrib.sessions.models import Session
import logging
from django.db.models import Q

MESSAGE_CACHE_SIZE = 75000

def cache_save_message(message):
    cache_set(message_cache_key(message.id), message, timeout=3600*24)

@cache_with_key(message_cache_key, timeout=3600*24)
def cache_get_message(message_id):
    return Message.objects.select_related().get(id=message_id)

def message_fetch_objects():
    try:
        max_id = Message.objects.only('id').order_by("-id")[0].id
    except IndexError:
        return []
    return Message.objects.select_related().filter(~Q(sender__email='tabbott/extra@mit.edu'),
                                                    id__gt=max_id - MESSAGE_CACHE_SIZE)

def message_cache_items(items_for_remote_cache, message):
    items_for_remote_cache[message_cache_key(message.id)] = (message,)

def user_cache_items(items_for_remote_cache, user_profile):
    items_for_remote_cache[user_profile_by_email_cache_key(user_profile.email)] = (user_profile,)
    items_for_remote_cache[user_profile_by_id_cache_key(user_profile.id)] = (user_profile,)

def stream_cache_items(items_for_remote_cache, stream):
    items_for_remote_cache[get_stream_cache_key(stream.name, stream.realm_id)] = (stream,)

def client_cache_items(items_for_remote_cache, client):
    items_for_remote_cache[get_client_cache_key(client.name)] = (client,)

def huddle_cache_items(items_for_remote_cache, huddle):
    items_for_remote_cache[huddle_hash_cache_key(huddle.huddle_hash)] = (huddle,)

def recipient_cache_items(items_for_remote_cache, recipient):
    items_for_remote_cache[get_recipient_cache_key(recipient.type, recipient.type_id)] = (recipient,)

session_engine = import_module(settings.SESSION_ENGINE)
def session_cache_items(items_for_remote_cache, session):
    store = session_engine.SessionStore(session_key=session.session_key)
    items_for_remote_cache[store.cache_key] = store.decode(session.session_data)

# Format is (objects query, items filler function, timeout, batch size)
#
# The objects queries are put inside lambdas to prevent Django from
# doing any setup for things we're unlikely to use (without the lambda
# wrapper the below adds an extra 3ms or so to startup time for
# anything importing this file).
cache_fillers = {
    'user': (lambda: UserProfile.objects.select_related().all(), user_cache_items, 3600*24*7, 10000),
    'client': (lambda: Client.objects.select_related().all(), client_cache_items, 3600*24*7, 10000),
    'recipient': (lambda: Recipient.objects.select_related().all(), recipient_cache_items, 3600*24*7, 10000),
    'stream': (lambda: Stream.objects.select_related().all(), stream_cache_items, 3600*24*7, 10000),
    'message': (message_fetch_objects, message_cache_items, 3600 * 24, 1000),
    'huddle': (lambda: Huddle.objects.select_related().all(), huddle_cache_items, 3600*24*7, 10000),
    'session': (lambda: Session.objects.all(), session_cache_items, 3600*24*7, 10000),
    }

def fill_remote_cache(cache):
    remote_cache_time_start = get_remote_cache_time()
    remote_cache_requests_start = get_remote_cache_requests()
    items_for_remote_cache = {} # type: Dict[str, Any]
    (objects, items_filler, timeout, batch_size) = cache_fillers[cache]
    count = 0
    for obj in objects():
        items_filler(items_for_remote_cache, obj)
        count += 1
        if (count % batch_size == 0):
            cache_set_many(items_for_remote_cache, timeout=3600*24)
            items_for_remote_cache = {}
    cache_set_many(items_for_remote_cache, timeout=3600*24*7)
    logging.info("Succesfully populated %s cache!  Consumed %s remote cache queries (%s time)" % \
                     (cache, get_remote_cache_requests() - remote_cache_requests_start,
                      round(get_remote_cache_time() - remote_cache_time_start, 2)))

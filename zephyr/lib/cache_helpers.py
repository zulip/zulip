# This file needs to be different from cache.py because cache.py
# cannot import anything from zephyr.models or we'd have an import
# loop
from zephyr.models import Message, UserProfile, Stream, get_stream_cache_key, \
    Recipient, get_recipient_cache_key
from zephyr.lib.cache import cache_with_key, djcache, message_cache_key, \
    user_profile_by_email_cache_key, user_profile_by_user_cache_key, \
    user_by_id_cache_key, user_profile_by_id_cache_key
import logging

MESSAGE_CACHE_SIZE = 25000

def cache_save_message(message):
    djcache.set(message_cache_key(message.id), (message,), timeout=3600*24)

@cache_with_key(message_cache_key)
def cache_get_message(message_id):
    return Message.objects.select_related().get(id=message_id)

# Called on Tornado startup to ensure our message cache isn't empty
def populate_message_cache():
    items_for_memcached = {}
    BATCH_SIZE = 1000
    count = 0
    for m in Message.objects.select_related().all().order_by("-id")[0:MESSAGE_CACHE_SIZE]:
        items_for_memcached[message_cache_key(m.id)] = (m,)
        count += 1
        if (count % BATCH_SIZE == 0):
            djcache.set_many(items_for_memcached, timeout=3600*24)
            items_for_memcached = {}

    djcache.set_many(items_for_memcached, timeout=3600*24)

# Fill our various caches of User/UserProfile objects used by Tornado
def populate_user_cache():
    items_for_memcached = {}
    for user_profile in UserProfile.objects.select_related().all():
        items_for_memcached[user_profile_by_email_cache_key(user_profile.user.email)] = (user_profile,)
        items_for_memcached[user_profile_by_user_cache_key(user_profile.user.id)] = (user_profile,)
        items_for_memcached[user_by_id_cache_key(user_profile.user.id)] = (user_profile.user,)
        items_for_memcached[user_profile_by_id_cache_key(user_profile.id)] = (user_profile,)

    djcache.set_many(items_for_memcached, timeout=3600*24*7)

def populate_stream_cache():
    items_for_memcached = {}
    for stream in Stream.objects.select_related().all():
        items_for_memcached[get_stream_cache_key(stream.name, stream.realm_id)] = (stream,)

    djcache.set_many(items_for_memcached, timeout=3600*24*7)

def populate_recipient_cache():
    items_for_memcached = {}
    for recipient in Recipient.objects.select_related().all():
        items_for_memcached[get_recipient_cache_key(recipient.type, recipient.type_id)] = (recipient,)

    djcache.set_many(items_for_memcached, timeout=3600*24*7)

def fill_memcached_caches():
    populate_user_cache()
    logging.info("Succesfully populated user cache!")
    populate_stream_cache()
    logging.info("Succesfully populated stream cache!")
    populate_recipient_cache()
    logging.info("Succesfully populated recipient cache!")
    populate_message_cache()
    logging.info("Succesfully populated mesasge cache!")

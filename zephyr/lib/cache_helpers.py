# This file needs to be different from cache.py because cache.py
# cannot import anything from zephyr.models or we'd have an import
# loop
from zephyr.models import Message, UserProfile
from zephyr.lib.cache import cache_with_key, djcache, message_cache_key, \
    userprofile_by_email_cache_key, userprofile_by_user_cache_key, \
    user_by_id_cache_key

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
        items_for_memcached[userprofile_by_email_cache_key(user_profile.user.email)] = (user_profile,)
        items_for_memcached[userprofile_by_user_cache_key(user_profile.user.id)] = (user_profile,)
        items_for_memcached[user_by_id_cache_key(user_profile.user.id)] = (user_profile.user,)

    djcache.set_many(items_for_memcached, timeout=3600*24*7)

def fill_memcached_caches():
    populate_user_cache()
    populate_message_cache()

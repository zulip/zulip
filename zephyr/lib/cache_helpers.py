# This file needs to be different from cache.py because cache.py
# cannot import anything from zephyr.models or we'd have an import
# loop
from zephyr.models import Message
from zephyr.lib.cache import cache_with_key, djcache, message_cache_key

MESSAGE_CACHE_SIZE = 25000

def cache_save_message(message):
    djcache.set(message_cache_key(message.id), (message,), timeout=3600*24)

@cache_with_key(message_cache_key)
def cache_get_message(message_id):
    return Message.objects.select_related("client", "sender").get(id=message_id)

# Called on Tornado startup to ensure our message cache isn't empty
def populate_message_cache():
    items_for_memcached = {}
    for m in Message.objects.select_related("sender", "client").all().order_by(
        "-id")[0:MESSAGE_CACHE_SIZE]:
        items_for_memcached[message_cache_key(m.id)] = (m,)

    djcache.set_many(items_for_memcached, timeout=3600*24)

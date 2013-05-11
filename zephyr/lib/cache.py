from __future__ import absolute_import

from functools import wraps

from django.core.cache import cache as djcache
from django.core.cache import get_cache

from zephyr.lib.utils import statsd, statsd_key, make_safe_digest
import time

memcached_time_start = 0
memcached_total_time = 0
memcached_total_requests = 0

def get_memcached_time():
    return memcached_total_time

def get_memcached_requests():
    return memcached_total_requests

def memcached_stats_start():
    global memcached_time_start
    memcached_time_start = time.time()

def memcached_stats_finish():
    global memcached_total_time
    global memcached_total_requests
    global memcached_time_start
    memcached_total_requests += 1
    memcached_total_time += (time.time() - memcached_time_start)

def cache_with_key(keyfunc, cache_name=None, timeout=None, with_statsd_key=None):
    """Decorator which applies Django caching to a function.

       Decorator argument is a function which computes a cache key
       from the original function's arguments.  You are responsible
       for avoiding collisions with other uses of this decorator or
       other uses of caching."""

    def decorator(func):
        @wraps(func)
        def func_with_caching(*args, **kwargs):
            key = keyfunc(*args, **kwargs)

            memcached_stats_start()
            if cache_name is None:
                cache_backend = djcache
            else:
                cache_backend = get_cache(cache_name)

            val = cache_backend.get(key)
            memcached_stats_finish()

            extra = ""
            if cache_name == 'database':
                extra = ".dbcache"

            if with_statsd_key is not None:
                metric_key = with_statsd_key
            else:
                metric_key = statsd_key(key)

            status = "hit" if val is not None else "miss"
            statsd.incr("cache%s.%s.%s" % (extra, metric_key, status))

            # Values are singleton tuples so that we can distinguish
            # a result of None from a missing key.
            if val is not None:
                return val[0]

            val = func(*args, **kwargs)

            memcached_stats_start()
            cache_backend.set(key, (val,), timeout=timeout)
            memcached_stats_finish()

            return val

        return func_with_caching

    return decorator

def cache_get_many(keys, cache_name=None):
    memcached_stats_start()
    if cache_name is None:
        cache_backend = djcache
    else:
        cache_backend = get_cache(cache_name)
    ret = cache_backend.get_many(keys)
    memcached_stats_finish()
    return ret

def cache_set_many(items, cache_name=None):
    memcached_stats_start()
    if cache_name is None:
        cache_backend = djcache
    else:
        cache_backend = get_cache(cache_name)
    ret = cache_backend.set_many(items)
    memcached_stats_finish()
    return ret

def cache(func):
    """Decorator which applies Django caching to a function.

       Uses a key based on the function's name, filename, and
       the repr() of its arguments."""

    func_uniqifier = '%s-%s' % (func.func_code.co_filename, func.func_name)

    @wraps(func)
    def keyfunc(*args, **kwargs):
        # Django complains about spaces because memcached rejects them
        key = func_uniqifier + repr((args, kwargs))
        return key.replace('-','--').replace(' ','-s')

    return cache_with_key(keyfunc)(func)

def message_cache_key(message_id):
    return "message:%d" % (message_id,)

def user_profile_by_email_cache_key(email):
    # See the comment in zephyr/lib/avatar.py:gravatar_hash for why we
    # are proactively encoding email addresses even though they will
    # with high likelihood be ASCII-only for the foreseeable future.
    return 'user_profile_by_email:%s' % (make_safe_digest(email),)

def user_profile_by_id_cache_key(user_profile_id):
    return "user_profile_by_id:%s" % (user_profile_id,)

# Called by models.py to flush the user_profile cache whenever we save
# a user_profile object
def update_user_profile_cache(sender, **kwargs):
    user_profile = kwargs['instance']
    items_for_memcached = {}
    items_for_memcached[user_profile_by_email_cache_key(user_profile.email)] = (user_profile,)
    items_for_memcached[user_profile_by_id_cache_key(user_profile.id)] = (user_profile,)
    djcache.set_many(items_for_memcached)

def status_dict_cache_key(user_profile):
    return "status_dict:%d" % (user_profile.realm_id,)

def update_user_presence_cache(sender, **kwargs):
    user_profile = kwargs['instance'].user_profile
    djcache.delete(status_dict_cache_key(user_profile))

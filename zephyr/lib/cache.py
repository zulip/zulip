from functools import wraps
import hashlib

from django.core.cache import cache as djcache
from django.core.cache import get_cache

def cache_with_key(keyfunc, cache_name=None, timeout=None):
    """Decorator which applies Django caching to a function.

       Decorator argument is a function which computes a cache key
       from the original function's arguments.  You are responsible
       for avoiding collisions with other uses of this decorator or
       other uses of caching."""

    def decorator(func):
        @wraps(func)
        def func_with_caching(*args, **kwargs):
            if cache_name is None:
                cache_backend = djcache
            else:
                cache_backend = get_cache(cache_name)

            key = keyfunc(*args, **kwargs)
            val = cache_backend.get(key)

            # Values are singleton tuples so that we can distinguish
            # a result of None from a missing key.
            if val is not None:
                return val[0]

            val = func(*args, **kwargs)
            cache_backend.set(key, (val,), timeout=timeout)
            return val

        return func_with_caching

    return decorator

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

def userprofile_by_email_cache_key(email):
    return 'user_profile_by_email:%s' % (hashlib.sha1(email).hexdigest(),)

def userprofile_by_user_cache_key(user_id):
    return 'user_profile_by_user_id:%d' % (user_id,)

def user_by_id_cache_key(user_id):
    return 'user_by_id:%d' % (user_id,)

# Called by models.py to flush the user_profile cache whenever we save
# a user_profile object
def update_user_profile_cache(sender, **kwargs):
    user_profile = kwargs['instance']
    items_for_memcached = {}
    items_for_memcached[userprofile_by_email_cache_key(user_profile.user.email)] = (user_profile,)
    items_for_memcached[userprofile_by_user_cache_key(user_profile.user.id)] = (user_profile,)
    djcache.set_many(items_for_memcached)

# Called by models.py to flush the user_profile cache whenever we save
# a user_profile object
def update_user_cache(sender, **kwargs):
    user = kwargs['instance']
    items_for_memcached = {}
    items_for_memcached[user_by_id_cache_key(user.id)] = (user,)
    djcache.set_many(items_for_memcached)


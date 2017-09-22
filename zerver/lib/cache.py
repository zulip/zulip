from __future__ import absolute_import
from __future__ import print_function

from functools import wraps

from django.core.cache import cache as djcache
from django.core.cache import caches
from django.conf import settings
from django.db.models import Q
from django.core.cache.backends.base import BaseCache

from typing import Any, Callable, Dict, Iterable, List, Optional, Union, TypeVar, Text

from zerver.lib.utils import statsd, statsd_key, make_safe_digest
import subprocess
import time
import base64
import random
import sys
import os
import hashlib
import six

if False:
    from zerver.models import UserProfile, Realm, Message
    # These modules have to be imported for type annotations but
    # they cannot be imported at runtime due to cyclic dependency.

FuncT = TypeVar('FuncT', bound=Callable[..., Any])

class NotFoundInCache(Exception):
    pass


remote_cache_time_start = 0.0
remote_cache_total_time = 0.0
remote_cache_total_requests = 0

def get_remote_cache_time():
    # type: () -> float
    return remote_cache_total_time

def get_remote_cache_requests():
    # type: () -> int
    return remote_cache_total_requests

def remote_cache_stats_start():
    # type: () -> None
    global remote_cache_time_start
    remote_cache_time_start = time.time()

def remote_cache_stats_finish():
    # type: () -> None
    global remote_cache_total_time
    global remote_cache_total_requests
    global remote_cache_time_start
    remote_cache_total_requests += 1
    remote_cache_total_time += (time.time() - remote_cache_time_start)

def get_or_create_key_prefix():
    # type: () -> Text
    if settings.CASPER_TESTS:
        # This sets the prefix for the benefit of the Casper tests.
        #
        # Having a fixed key is OK since we don't support running
        # multiple copies of the casper tests at the same time anyway.
        return u'casper_tests:'
    elif settings.TEST_SUITE:
        # The Python tests overwrite KEY_PREFIX on each test, but use
        # this codepath as well, just to save running the more complex
        # code below for reading the normal key prefix.
        return u'django_tests_unused:'

    # directory `var` should exist in production
    subprocess.check_call(["mkdir", "-p", os.path.join(settings.DEPLOY_ROOT, "var")])

    filename = os.path.join(settings.DEPLOY_ROOT, "var", "remote_cache_prefix")
    try:
        fd = os.open(filename, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o444)
        random_hash = hashlib.sha256(Text(random.getrandbits(256)).encode('utf-8')).digest()
        prefix = base64.b16encode(random_hash)[:32].decode('utf-8').lower() + ':'
        # This does close the underlying file
        with os.fdopen(fd, 'w') as f:
            f.write(prefix + "\n")
    except OSError:
        # The file already exists
        tries = 1
        while tries < 10:
            with open(filename, 'r') as f:
                prefix = f.readline()[:-1]
            if len(prefix) == 33:
                break
            tries += 1
            prefix = ''
            time.sleep(0.5)

    if not prefix:
        print("Could not read remote cache key prefix file")
        sys.exit(1)

    return prefix

KEY_PREFIX = get_or_create_key_prefix()  # type: Text

def bounce_key_prefix_for_testing(test_name):
    # type: (Text) -> None
    global KEY_PREFIX
    KEY_PREFIX = test_name + u':' + Text(os.getpid()) + u':'
    # We are taking the hash of the KEY_PREFIX to decrease the size of the key.
    # Memcached keys should have a length of less than 256.
    KEY_PREFIX = hashlib.sha1(KEY_PREFIX.encode('utf-8')).hexdigest()

def get_cache_backend(cache_name):
    # type: (Optional[str]) -> BaseCache
    if cache_name is None:
        return djcache
    return caches[cache_name]

def get_cache_with_key(keyfunc, cache_name=None):
    # type: (Any, Optional[str]) -> Any
    """
    The main goal of this function getting value from the cache like in the "cache_with_key".
    A cache value can contain any data including the "None", so
    here used exception for case if value isn't found in the cache.
    """
    def decorator(func):
        # type: (Callable[..., Any]) -> (Callable[..., Any])
        @wraps(func)
        def func_with_caching(*args, **kwargs):
            # type: (*Any, **Any) -> Callable[..., Any]
            key = keyfunc(*args, **kwargs)
            val = cache_get(key, cache_name=cache_name)
            if val is not None:
                return val[0]
            raise NotFoundInCache()

        return func_with_caching

    return decorator

def cache_with_key(keyfunc, cache_name=None, timeout=None, with_statsd_key=None):
    # type: (Any, Optional[str], Optional[int], Optional[str]) -> Any
    # This function can't be typed perfectly because returning a generic function
    # isn't supported in mypy - https://github.com/python/mypy/issues/1551.
    """Decorator which applies Django caching to a function.

       Decorator argument is a function which computes a cache key
       from the original function's arguments.  You are responsible
       for avoiding collisions with other uses of this decorator or
       other uses of caching."""

    def decorator(func):
        # type: (Callable[..., Any]) -> (Callable[..., Any])
        @wraps(func)
        def func_with_caching(*args, **kwargs):
            # type: (*Any, **Any) -> Any
            key = keyfunc(*args, **kwargs)

            val = cache_get(key, cache_name=cache_name)

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

            cache_set(key, val, cache_name=cache_name, timeout=timeout)

            return val

        return func_with_caching

    return decorator

def cache_set(key, val, cache_name=None, timeout=None):
    # type: (Text, Any, Optional[str], Optional[int]) -> None
    remote_cache_stats_start()
    cache_backend = get_cache_backend(cache_name)
    cache_backend.set(KEY_PREFIX + key, (val,), timeout=timeout)
    remote_cache_stats_finish()

def cache_get(key, cache_name=None):
    # type: (Text, Optional[str]) -> Any
    remote_cache_stats_start()
    cache_backend = get_cache_backend(cache_name)
    ret = cache_backend.get(KEY_PREFIX + key)
    remote_cache_stats_finish()
    return ret

def cache_get_many(keys, cache_name=None):
    # type: (List[Text], Optional[str]) -> Dict[Text, Any]
    keys = [KEY_PREFIX + key for key in keys]
    remote_cache_stats_start()
    ret = get_cache_backend(cache_name).get_many(keys)
    remote_cache_stats_finish()
    return dict([(key[len(KEY_PREFIX):], value) for key, value in ret.items()])

def cache_set_many(items, cache_name=None, timeout=None):
    # type: (Dict[Text, Any], Optional[str], Optional[int]) -> None
    new_items = {}
    for key in items:
        new_items[KEY_PREFIX + key] = items[key]
    items = new_items
    remote_cache_stats_start()
    get_cache_backend(cache_name).set_many(items, timeout=timeout)
    remote_cache_stats_finish()

def cache_delete(key, cache_name=None):
    # type: (Text, Optional[str]) -> None
    remote_cache_stats_start()
    get_cache_backend(cache_name).delete(KEY_PREFIX + key)
    remote_cache_stats_finish()

def cache_delete_many(items, cache_name=None):
    # type: (Iterable[Text], Optional[str]) -> None
    remote_cache_stats_start()
    get_cache_backend(cache_name).delete_many(
        KEY_PREFIX + item for item in items)
    remote_cache_stats_finish()

# Required Arguments are as follows:
# * object_ids: The list of object ids to look up
# * cache_key_function: object_id => cache key
# * query_function: [object_ids] => [objects from database]
# Optional keyword arguments:
# * setter: Function to call before storing items to cache (e.g. compression)
# * extractor: Function to call on items returned from cache
#   (e.g. decompression).  Should be the inverse of the setter
#   function.
# * id_fetcher: Function mapping an object from database => object_id
#   (in case we're using a key more complex than obj.id)
# * cache_transformer: Function mapping an object from database =>
#   value for cache (in case the values that we're caching are some
#   function of the objects, not the objects themselves)
ObjKT = TypeVar('ObjKT', int, Text)
ItemT = Any  # https://github.com/python/mypy/issues/1721
CompressedItemT = Any  # https://github.com/python/mypy/issues/1721
def generic_bulk_cached_fetch(cache_key_function,  # type: Callable[[ObjKT], Text]
                              query_function,  # type: Callable[[List[ObjKT]], Iterable[Any]]
                              object_ids,  # type: Iterable[ObjKT]
                              extractor=lambda obj: obj,  # type: Callable[[CompressedItemT], ItemT]
                              setter=lambda obj: obj,  # type: Callable[[ItemT], CompressedItemT]
                              id_fetcher=lambda obj: obj.id,  # type: Callable[[Any], ObjKT]
                              cache_transformer=lambda obj: obj  # type: Callable[[Any], ItemT]
                              ):
    # type: (...) -> Dict[ObjKT, Any]
    cache_keys = {}  # type: Dict[ObjKT, Text]
    for object_id in object_ids:
        cache_keys[object_id] = cache_key_function(object_id)
    cached_objects = cache_get_many([cache_keys[object_id]
                                     for object_id in object_ids])
    for (key, val) in cached_objects.items():
        cached_objects[key] = extractor(cached_objects[key][0])
    needed_ids = [object_id for object_id in object_ids if
                  cache_keys[object_id] not in cached_objects]
    db_objects = query_function(needed_ids)

    items_for_remote_cache = {}  # type: Dict[Text, Any]
    for obj in db_objects:
        key = cache_keys[id_fetcher(obj)]
        item = cache_transformer(obj)
        items_for_remote_cache[key] = (setter(item),)
        cached_objects[key] = item
    if len(items_for_remote_cache) > 0:
        cache_set_many(items_for_remote_cache)
    return dict((object_id, cached_objects[cache_keys[object_id]]) for object_id in object_ids
                if cache_keys[object_id] in cached_objects)

def cache(func):
    # type: (FuncT) -> FuncT
    """Decorator which applies Django caching to a function.

       Uses a key based on the function's name, filename, and
       the repr() of its arguments."""

    func_uniqifier = '%s-%s' % (func.__code__.co_filename, func.__name__)

    @wraps(func)
    def keyfunc(*args, **kwargs):
        # type: (*Any, **Any) -> str
        # Django complains about spaces because memcached rejects them
        key = func_uniqifier + repr((args, kwargs))
        return key.replace('-', '--').replace(' ', '-s')

    return cache_with_key(keyfunc)(func)

def display_recipient_cache_key(recipient_id):
    # type: (int) -> Text
    return u"display_recipient_dict:%d" % (recipient_id,)

def user_profile_by_email_cache_key(email):
    # type: (Text) -> Text
    # See the comment in zerver/lib/avatar_hash.py:gravatar_hash for why we
    # are proactively encoding email addresses even though they will
    # with high likelihood be ASCII-only for the foreseeable future.
    return u'user_profile_by_email:%s' % (make_safe_digest(email.strip()),)

def user_profile_cache_key(email, realm):
    # type: (Text, Realm) -> Text
    return u"user_profile:%s:%s" % (make_safe_digest(email.strip()), realm.id,)

def bot_profile_cache_key(email):
    # type: (Text) -> Text
    return u"bot_profile:%s" % (make_safe_digest(email.strip()))

def user_profile_by_id_cache_key(user_profile_id):
    # type: (int) -> Text
    return u"user_profile_by_id:%s" % (user_profile_id,)

def user_profile_by_api_key_cache_key(api_key):
    # type: (Text) -> Text
    return u"user_profile_by_api_key:%s" % (api_key,)

# TODO: Refactor these cache helpers into another file that can import
# models.py so that python v3 style type annotations can also work.

active_user_dict_fields = [
    'id', 'full_name', 'short_name', 'email',
    'avatar_source', 'avatar_version',
    'is_realm_admin', 'is_bot', 'realm_id', 'timezone']  # type: List[str]

def active_user_dicts_in_realm_cache_key(realm_id):
    # type: (int) -> Text
    return u"active_user_dicts_in_realm:%s" % (realm_id,)

def active_user_ids_cache_key(realm_id):
    # type: (int) -> Text
    return u"active_user_ids:%s" % (realm_id,)

bot_dict_fields = ['id', 'full_name', 'short_name', 'bot_type', 'email',
                   'is_active', 'default_sending_stream__name',
                   'realm_id',
                   'default_events_register_stream__name',
                   'default_all_public_streams', 'api_key',
                   'bot_owner__email', 'avatar_source',
                   'avatar_version']  # type: List[str]

def bot_dicts_in_realm_cache_key(realm):
    # type: (Realm) -> Text
    return u"bot_dicts_in_realm:%s" % (realm.id,)

def get_stream_cache_key(stream_name, realm_id):
    # type: (Text, int) -> Text
    return u"stream_by_realm_and_name:%s:%s" % (
        realm_id, make_safe_digest(stream_name.strip().lower()))

def delete_user_profile_caches(user_profiles):
    # type: (Iterable[UserProfile]) -> None
    keys = []
    for user_profile in user_profiles:
        keys.append(user_profile_by_email_cache_key(user_profile.email))
        keys.append(user_profile_by_id_cache_key(user_profile.id))
        keys.append(user_profile_by_api_key_cache_key(user_profile.api_key))
        keys.append(user_profile_cache_key(user_profile.email, user_profile.realm))

    cache_delete_many(keys)

def delete_display_recipient_cache(user_profile):
    # type: (UserProfile) -> None
    from zerver.models import Subscription  # We need to import here to avoid cyclic dependency.
    recipient_ids = Subscription.objects.filter(user_profile=user_profile)
    recipient_ids = recipient_ids.values_list('recipient_id', flat=True)
    keys = [display_recipient_cache_key(rid) for rid in recipient_ids]
    cache_delete_many(keys)

# Called by models.py to flush the user_profile cache whenever we save
# a user_profile object
def flush_user_profile(sender, **kwargs):
    # type: (Any, **Any) -> None
    user_profile = kwargs['instance']
    delete_user_profile_caches([user_profile])

    # Invalidate our active_users_in_realm info dict if any user has changed
    # the fields in the dict or become (in)active
    if kwargs.get('update_fields') is None or \
            len(set(active_user_dict_fields + ['is_active', 'email']) &
                set(kwargs['update_fields'])) > 0:
        cache_delete(active_user_dicts_in_realm_cache_key(user_profile.realm_id))

    if kwargs.get('update_fields') is None or \
            ('is_active' in kwargs['update_fields']):
        cache_delete(active_user_ids_cache_key(user_profile.realm_id))

    if kwargs.get('updated_fields') is None or \
            'email' in kwargs['update_fields']:
        delete_display_recipient_cache(user_profile)

    # Invalidate our bots_in_realm info dict if any bot has
    # changed the fields in the dict or become (in)active
    if user_profile.is_bot and (kwargs['update_fields'] is None or
                                (set(bot_dict_fields) & set(kwargs['update_fields']))):
        cache_delete(bot_dicts_in_realm_cache_key(user_profile.realm))

    # Invalidate realm-wide alert words cache if any user in the realm has changed
    # alert words
    if kwargs.get('update_fields') is None or "alert_words" in kwargs['update_fields']:
        cache_delete(realm_alert_words_cache_key(user_profile.realm))

# Called by models.py to flush various caches whenever we save
# a Realm object.  The main tricky thing here is that Realm info is
# generally cached indirectly through user_profile objects.
def flush_realm(sender, **kwargs):
    # type: (Any, **Any) -> None
    realm = kwargs['instance']
    users = realm.get_active_users()
    delete_user_profile_caches(users)

    if realm.deactivated:
        cache_delete(active_user_dicts_in_realm_cache_key(realm.id))
        cache_delete(active_user_ids_cache_key(realm.id))
        cache_delete(bot_dicts_in_realm_cache_key(realm))
        cache_delete(realm_alert_words_cache_key(realm))

def realm_alert_words_cache_key(realm):
    # type: (Realm) -> Text
    return u"realm_alert_words:%s" % (realm.string_id,)

# Called by models.py to flush the stream cache whenever we save a stream
# object.
def flush_stream(sender, **kwargs):
    # type: (Any, **Any) -> None
    from zerver.models import UserProfile
    stream = kwargs['instance']
    items_for_remote_cache = {}
    items_for_remote_cache[get_stream_cache_key(stream.name, stream.realm_id)] = (stream,)
    cache_set_many(items_for_remote_cache)

    if kwargs.get('update_fields') is None or 'name' in kwargs['update_fields'] and \
       UserProfile.objects.filter(
           Q(default_sending_stream=stream) |
           Q(default_events_register_stream=stream)).exists():
        cache_delete(bot_dicts_in_realm_cache_key(stream.realm))

# TODO: Rename to_dict_cache_key_id and to_dict_cache_key
def to_dict_cache_key_id(message_id, apply_markdown):
    # type: (int, bool) -> Text
    return u'message_dict:%d:%d' % (message_id, apply_markdown)

def to_dict_cache_key(message, apply_markdown):
    # type: (Message, bool) -> Text
    return to_dict_cache_key_id(message.id, apply_markdown)

def flush_message(sender, **kwargs):
    # type: (Any, **Any) -> None
    message = kwargs['instance']
    cache_delete(to_dict_cache_key(message, False))
    cache_delete(to_dict_cache_key(message, True))

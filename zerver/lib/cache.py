# See https://zulip.readthedocs.io/en/latest/subsystems/caching.html for docs
from functools import wraps

from django.utils.lru_cache import lru_cache
from django.core.cache import cache as djcache
from django.core.cache import caches
from django.conf import settings
from django.db.models import Q
from django.core.cache.backends.base import BaseCache
from django.http import HttpRequest

from typing import Any, Callable, Dict, Iterable, List, Optional, TypeVar, Tuple

from zerver.lib.utils import statsd, statsd_key, make_safe_digest
import time
import base64
import random
import sys
import os
import hashlib

if False:
    # These modules have to be imported for type annotations but
    # they cannot be imported at runtime due to cyclic dependency.
    from zerver.models import UserProfile, Realm, Message

ReturnT = TypeVar('ReturnT')  # Useful for matching return types via Callable[..., ReturnT]

class NotFoundInCache(Exception):
    pass


remote_cache_time_start = 0.0
remote_cache_total_time = 0.0
remote_cache_total_requests = 0

def get_remote_cache_time() -> float:
    return remote_cache_total_time

def get_remote_cache_requests() -> int:
    return remote_cache_total_requests

def remote_cache_stats_start() -> None:
    global remote_cache_time_start
    remote_cache_time_start = time.time()

def remote_cache_stats_finish() -> None:
    global remote_cache_total_time
    global remote_cache_total_requests
    global remote_cache_time_start
    remote_cache_total_requests += 1
    remote_cache_total_time += (time.time() - remote_cache_time_start)

def get_or_create_key_prefix() -> str:
    if settings.CASPER_TESTS:
        # This sets the prefix for the benefit of the Casper tests.
        #
        # Having a fixed key is OK since we don't support running
        # multiple copies of the casper tests at the same time anyway.
        return 'casper_tests:'
    elif settings.TEST_SUITE:
        # The Python tests overwrite KEY_PREFIX on each test, but use
        # this codepath as well, just to save running the more complex
        # code below for reading the normal key prefix.
        return 'django_tests_unused:'

    # directory `var` should exist in production
    os.makedirs(os.path.join(settings.DEPLOY_ROOT, "var"), exist_ok=True)

    filename = os.path.join(settings.DEPLOY_ROOT, "var", "remote_cache_prefix")
    try:
        fd = os.open(filename, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o444)
        random_hash = hashlib.sha256(str(random.getrandbits(256)).encode('utf-8')).digest()
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

KEY_PREFIX = get_or_create_key_prefix()  # type: str

def bounce_key_prefix_for_testing(test_name: str) -> None:
    global KEY_PREFIX
    KEY_PREFIX = test_name + ':' + str(os.getpid()) + ':'
    # We are taking the hash of the KEY_PREFIX to decrease the size of the key.
    # Memcached keys should have a length of less than 256.
    KEY_PREFIX = hashlib.sha1(KEY_PREFIX.encode('utf-8')).hexdigest()

def get_cache_backend(cache_name: Optional[str]) -> BaseCache:
    if cache_name is None:
        return djcache
    return caches[cache_name]

def get_cache_with_key(
        keyfunc: Callable[..., str],
        cache_name: Optional[str]=None
) -> Callable[[Callable[..., ReturnT]], Callable[..., ReturnT]]:
    """
    The main goal of this function getting value from the cache like in the "cache_with_key".
    A cache value can contain any data including the "None", so
    here used exception for case if value isn't found in the cache.
    """
    def decorator(func: Callable[..., ReturnT]) -> (Callable[..., ReturnT]):
        @wraps(func)
        def func_with_caching(*args: Any, **kwargs: Any) -> Callable[..., ReturnT]:
            key = keyfunc(*args, **kwargs)
            val = cache_get(key, cache_name=cache_name)
            if val is not None:
                return val[0]
            raise NotFoundInCache()

        return func_with_caching

    return decorator

def cache_with_key(
        keyfunc: Callable[..., str], cache_name: Optional[str]=None,
        timeout: Optional[int]=None, with_statsd_key: Optional[str]=None
) -> Callable[[Callable[..., ReturnT]], Callable[..., ReturnT]]:
    """Decorator which applies Django caching to a function.

       Decorator argument is a function which computes a cache key
       from the original function's arguments.  You are responsible
       for avoiding collisions with other uses of this decorator or
       other uses of caching."""

    def decorator(func: Callable[..., ReturnT]) -> Callable[..., ReturnT]:
        @wraps(func)
        def func_with_caching(*args: Any, **kwargs: Any) -> ReturnT:
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

def cache_set(key: str, val: Any, cache_name: Optional[str]=None, timeout: Optional[int]=None) -> None:
    remote_cache_stats_start()
    cache_backend = get_cache_backend(cache_name)
    cache_backend.set(KEY_PREFIX + key, (val,), timeout=timeout)
    remote_cache_stats_finish()

def cache_get(key: str, cache_name: Optional[str]=None) -> Any:
    remote_cache_stats_start()
    cache_backend = get_cache_backend(cache_name)
    ret = cache_backend.get(KEY_PREFIX + key)
    remote_cache_stats_finish()
    return ret

def cache_get_many(keys: List[str], cache_name: Optional[str]=None) -> Dict[str, Any]:
    keys = [KEY_PREFIX + key for key in keys]
    remote_cache_stats_start()
    ret = get_cache_backend(cache_name).get_many(keys)
    remote_cache_stats_finish()
    return dict([(key[len(KEY_PREFIX):], value) for key, value in ret.items()])

def cache_set_many(items: Dict[str, Any], cache_name: Optional[str]=None,
                   timeout: Optional[int]=None) -> None:
    new_items = {}
    for key in items:
        new_items[KEY_PREFIX + key] = items[key]
    items = new_items
    remote_cache_stats_start()
    get_cache_backend(cache_name).set_many(items, timeout=timeout)
    remote_cache_stats_finish()

def cache_delete(key: str, cache_name: Optional[str]=None) -> None:
    remote_cache_stats_start()
    get_cache_backend(cache_name).delete(KEY_PREFIX + key)
    remote_cache_stats_finish()

def cache_delete_many(items: Iterable[str], cache_name: Optional[str]=None) -> None:
    remote_cache_stats_start()
    get_cache_backend(cache_name).delete_many(
        KEY_PREFIX + item for item in items)
    remote_cache_stats_finish()

# Generic_bulk_cached fetch and its helpers
ObjKT = TypeVar('ObjKT')
ItemT = TypeVar('ItemT')
CompressedItemT = TypeVar('CompressedItemT')

def default_extractor(obj: CompressedItemT) -> ItemT:
    return obj  # type: ignore # Need a type assert that ItemT=CompressedItemT

def default_setter(obj: ItemT) -> CompressedItemT:
    return obj  # type: ignore # Need a type assert that ItemT=CompressedItemT

def default_id_fetcher(obj: ItemT) -> ObjKT:
    return obj.id  # type: ignore # Need ItemT/CompressedItemT typevars to be a Django protocol

def default_cache_transformer(obj: ItemT) -> ItemT:
    return obj

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
def generic_bulk_cached_fetch(
        cache_key_function: Callable[[ObjKT], str],
        query_function: Callable[[List[ObjKT]], Iterable[Any]],
        object_ids: Iterable[ObjKT],
        extractor: Callable[[CompressedItemT], ItemT] = default_extractor,
        setter: Callable[[ItemT], CompressedItemT] = default_setter,
        id_fetcher: Callable[[ItemT], ObjKT] = default_id_fetcher,
        cache_transformer: Callable[[ItemT], ItemT] = default_cache_transformer
) -> Dict[ObjKT, ItemT]:
    cache_keys = {}  # type: Dict[ObjKT, str]
    for object_id in object_ids:
        cache_keys[object_id] = cache_key_function(object_id)
    cached_objects_compressed = cache_get_many([cache_keys[object_id]
                                                for object_id in object_ids])  # type: Dict[str, Tuple[CompressedItemT]]
    cached_objects = {}  # type: Dict[str, ItemT]
    for (key, val) in cached_objects_compressed.items():
        cached_objects[key] = extractor(cached_objects_compressed[key][0])
    needed_ids = [object_id for object_id in object_ids if
                  cache_keys[object_id] not in cached_objects]
    db_objects = query_function(needed_ids)

    items_for_remote_cache = {}  # type: Dict[str, Tuple[CompressedItemT]]
    for obj in db_objects:
        key = cache_keys[id_fetcher(obj)]
        item = cache_transformer(obj)
        items_for_remote_cache[key] = (setter(item),)
        cached_objects[key] = item
    if len(items_for_remote_cache) > 0:
        cache_set_many(items_for_remote_cache)
    return dict((object_id, cached_objects[cache_keys[object_id]]) for object_id in object_ids
                if cache_keys[object_id] in cached_objects)

def cache(func: Callable[..., ReturnT]) -> Callable[..., ReturnT]:
    """Decorator which applies Django caching to a function.

       Uses a key based on the function's name, filename, and
       the repr() of its arguments."""

    func_uniqifier = '%s-%s' % (func.__code__.co_filename, func.__name__)

    @wraps(func)
    def keyfunc(*args: Any, **kwargs: Any) -> str:
        # Django complains about spaces because memcached rejects them
        key = func_uniqifier + repr((args, kwargs))
        return key.replace('-', '--').replace(' ', '-s')

    return cache_with_key(keyfunc)(func)

def preview_url_cache_key(url: str) -> str:
    return "preview_url:%s" % (make_safe_digest(url))

def display_recipient_cache_key(recipient_id: int) -> str:
    return "display_recipient_dict:%d" % (recipient_id,)

def user_profile_by_email_cache_key(email: str) -> str:
    # See the comment in zerver/lib/avatar_hash.py:gravatar_hash for why we
    # are proactively encoding email addresses even though they will
    # with high likelihood be ASCII-only for the foreseeable future.
    return 'user_profile_by_email:%s' % (make_safe_digest(email.strip()),)

def user_profile_cache_key_id(email: str, realm_id: int) -> str:
    return u"user_profile:%s:%s" % (make_safe_digest(email.strip()), realm_id,)

def user_profile_cache_key(email: str, realm: 'Realm') -> str:
    return user_profile_cache_key_id(email, realm.id)

def bot_profile_cache_key(email: str) -> str:
    return "bot_profile:%s" % (make_safe_digest(email.strip()))

def user_profile_by_id_cache_key(user_profile_id: int) -> str:
    return "user_profile_by_id:%s" % (user_profile_id,)

def user_profile_by_api_key_cache_key(api_key: str) -> str:
    return "user_profile_by_api_key:%s" % (api_key,)

realm_user_dict_fields = [
    'id', 'full_name', 'short_name', 'email',
    'avatar_source', 'avatar_version', 'is_active',
    'is_realm_admin', 'is_bot', 'realm_id', 'timezone',
    'date_joined', 'is_guest'
]  # type: List[str]

def realm_user_dicts_cache_key(realm_id: int) -> str:
    return "realm_user_dicts:%s" % (realm_id,)

def get_realm_used_upload_space_cache_key(realm: 'Realm') -> str:
    return u'realm_used_upload_space:%s' % (realm.id,)

def active_user_ids_cache_key(realm_id: int) -> str:
    return "active_user_ids:%s" % (realm_id,)

def active_non_guest_user_ids_cache_key(realm_id: int) -> str:
    return "active_non_guest_user_ids:%s" % (realm_id,)

bot_dict_fields = ['id', 'full_name', 'short_name', 'bot_type', 'email',
                   'is_active', 'default_sending_stream__name',
                   'realm_id',
                   'default_events_register_stream__name',
                   'default_all_public_streams', 'api_key',
                   'bot_owner__email', 'avatar_source',
                   'avatar_version']  # type: List[str]

def bot_dicts_in_realm_cache_key(realm: 'Realm') -> str:
    return "bot_dicts_in_realm:%s" % (realm.id,)

def get_stream_cache_key(stream_name: str, realm_id: int) -> str:
    return "stream_by_realm_and_name:%s:%s" % (
        realm_id, make_safe_digest(stream_name.strip().lower()))

def delete_user_profile_caches(user_profiles: Iterable['UserProfile']) -> None:
    # Imported here to avoid cyclic dependency.
    from zerver.lib.users import get_all_api_keys
    keys = []
    for user_profile in user_profiles:
        keys.append(user_profile_by_email_cache_key(user_profile.delivery_email))
        keys.append(user_profile_by_id_cache_key(user_profile.id))
        for api_key in get_all_api_keys(user_profile):
            keys.append(user_profile_by_api_key_cache_key(api_key))
        keys.append(user_profile_cache_key(user_profile.email, user_profile.realm))

    cache_delete_many(keys)

def delete_display_recipient_cache(user_profile: 'UserProfile') -> None:
    from zerver.models import Subscription  # We need to import here to avoid cyclic dependency.
    recipient_ids = Subscription.objects.filter(user_profile=user_profile)
    recipient_ids = recipient_ids.values_list('recipient_id', flat=True)
    keys = [display_recipient_cache_key(rid) for rid in recipient_ids]
    cache_delete_many(keys)

# Called by models.py to flush the user_profile cache whenever we save
# a user_profile object
def flush_user_profile(sender: Any, **kwargs: Any) -> None:
    user_profile = kwargs['instance']
    delete_user_profile_caches([user_profile])

    def changed(fields: List[str]) -> bool:
        if kwargs.get('update_fields') is None:
            # adds/deletes should invalidate the cache
            return True

        update_fields = set(kwargs['update_fields'])
        for f in fields:
            if f in update_fields:
                return True

        return False

    # Invalidate our active_users_in_realm info dict if any user has changed
    # the fields in the dict or become (in)active
    if changed(realm_user_dict_fields):
        cache_delete(realm_user_dicts_cache_key(user_profile.realm_id))

    if changed(['is_active']):
        cache_delete(active_user_ids_cache_key(user_profile.realm_id))
        cache_delete(active_non_guest_user_ids_cache_key(user_profile.realm_id))

    if changed(['is_guest']):
        cache_delete(active_non_guest_user_ids_cache_key(user_profile.realm_id))

    if changed(['email', 'full_name', 'short_name', 'id', 'is_mirror_dummy']):
        delete_display_recipient_cache(user_profile)

    # Invalidate our bots_in_realm info dict if any bot has
    # changed the fields in the dict or become (in)active
    if user_profile.is_bot and changed(bot_dict_fields):
        cache_delete(bot_dicts_in_realm_cache_key(user_profile.realm))

    # Invalidate realm-wide alert words cache if any user in the realm has changed
    # alert words
    if changed(['alert_words']):
        cache_delete(realm_alert_words_cache_key(user_profile.realm))
        cache_delete(realm_alert_words_automaton_cache_key(user_profile.realm))

# Called by models.py to flush various caches whenever we save
# a Realm object.  The main tricky thing here is that Realm info is
# generally cached indirectly through user_profile objects.
def flush_realm(sender: Any, **kwargs: Any) -> None:
    realm = kwargs['instance']
    users = realm.get_active_users()
    delete_user_profile_caches(users)

    if realm.deactivated or (kwargs["update_fields"] is not None and
                             "string_id" in kwargs['update_fields']):
        cache_delete(realm_user_dicts_cache_key(realm.id))
        cache_delete(active_user_ids_cache_key(realm.id))
        cache_delete(bot_dicts_in_realm_cache_key(realm))
        cache_delete(realm_alert_words_cache_key(realm))
        cache_delete(realm_alert_words_automaton_cache_key(realm))
        cache_delete(active_non_guest_user_ids_cache_key(realm.id))

def realm_alert_words_cache_key(realm: 'Realm') -> str:
    return "realm_alert_words:%s" % (realm.string_id,)

def realm_alert_words_automaton_cache_key(realm: 'Realm') -> str:
    return "realm_alert_words_automaton:%s" % (realm.string_id,)

# Called by models.py to flush the stream cache whenever we save a stream
# object.
def flush_stream(sender: Any, **kwargs: Any) -> None:
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

def flush_used_upload_space_cache(sender: Any, **kwargs: Any) -> None:
    attachment = kwargs['instance']

    if kwargs.get("created") is None or kwargs.get("created") is True:
        cache_delete(get_realm_used_upload_space_cache_key(attachment.owner.realm))

def to_dict_cache_key_id(message_id: int) -> str:
    return 'message_dict:%d' % (message_id,)

def to_dict_cache_key(message: 'Message') -> str:
    return to_dict_cache_key_id(message.id)

def open_graph_description_cache_key(content: Any, request: HttpRequest) -> str:
    return 'open_graph_description_path:%s' % (make_safe_digest(request.META['PATH_INFO']))

def flush_message(sender: Any, **kwargs: Any) -> None:
    message = kwargs['instance']
    cache_delete(to_dict_cache_key_id(message.id))

def flush_submessage(sender: Any, **kwargs: Any) -> None:
    submessage = kwargs['instance']
    # submessages are not cached directly, they are part of their
    # parent messages
    message_id = submessage.message_id
    cache_delete(to_dict_cache_key_id(message_id))

DECORATOR = Callable[[Callable[..., Any]], Callable[..., Any]]

def ignore_unhashable_lru_cache(maxsize: int=128, typed: bool=False) -> DECORATOR:
    """
    This is a wrapper over lru_cache function. It adds following features on
    top of lru_cache:

        * It will not cache result of functions with unhashable arguments.
        * It will clear cache whenever zerver.lib.cache.KEY_PREFIX changes.
    """
    internal_decorator = lru_cache(maxsize=maxsize, typed=typed)

    def decorator(user_function: Callable[..., Any]) -> Callable[..., Any]:
        if settings.DEVELOPMENT and not settings.TEST_SUITE:  # nocoverage
            # In the development environment, we want every file
            # change to refresh the source files from disk.
            return user_function
        cache_enabled_user_function = internal_decorator(user_function)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not hasattr(cache_enabled_user_function, 'key_prefix'):
                cache_enabled_user_function.key_prefix = KEY_PREFIX

            if cache_enabled_user_function.key_prefix != KEY_PREFIX:
                # Clear cache when cache.KEY_PREFIX changes. This is used in
                # tests.
                cache_enabled_user_function.cache_clear()
                cache_enabled_user_function.key_prefix = KEY_PREFIX

            try:
                return cache_enabled_user_function(*args, **kwargs)
            except TypeError:
                # args or kwargs contains an element which is unhashable. In
                # this case we don't cache the result.
                pass

            # Deliberately calling this function from outside of exception
            # handler to get a more descriptive traceback. Otherise traceback
            # can include the exception from cached_enabled_user_function as
            # well.
            return user_function(*args, **kwargs)

        setattr(wrapper, 'cache_info', cache_enabled_user_function.cache_info)
        setattr(wrapper, 'cache_clear', cache_enabled_user_function.cache_clear)
        return wrapper

    return decorator

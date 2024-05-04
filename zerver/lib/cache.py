# See https://zulip.readthedocs.io/en/latest/subsystems/caching.html for docs
import hashlib
import logging
import os
import re
import secrets
import sys
import time
import traceback
from functools import _lru_cache_wrapper, lru_cache, wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
)

from django.conf import settings
from django.core.cache import caches
from django.core.cache.backends.base import BaseCache
from django.db.models import Q
from django_stubs_ext import QuerySetAny
from typing_extensions import ParamSpec

if TYPE_CHECKING:
    # These modules have to be imported for type annotations but
    # they cannot be imported at runtime due to cyclic dependency.
    from zerver.models import Attachment, Message, MutedUser, Realm, Stream, SubMessage, UserProfile

MEMCACHED_MAX_KEY_LENGTH = 250

ParamT = ParamSpec("ParamT")
ReturnT = TypeVar("ReturnT")

logger = logging.getLogger()

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
    remote_cache_total_requests += 1
    remote_cache_total_time += time.time() - remote_cache_time_start


def get_or_create_key_prefix() -> str:
    if settings.PUPPETEER_TESTS:
        # This sets the prefix for the benefit of the Puppeteer tests.
        #
        # Having a fixed key is OK since we don't support running
        # multiple copies of the Puppeteer tests at the same time anyway.
        return "puppeteer_tests:"
    elif settings.TEST_SUITE:
        # The Python tests overwrite KEY_PREFIX on each test, but use
        # this codepath as well, just to save running the more complex
        # code below for reading the normal key prefix.
        return "django_tests_unused:"

    # directory `var` should exist in production
    os.makedirs(os.path.join(settings.DEPLOY_ROOT, "var"), exist_ok=True)

    filename = os.path.join(settings.DEPLOY_ROOT, "var", "remote_cache_prefix")
    try:
        with open(filename, "x") as f:
            prefix = secrets.token_hex(16) + ":"
            f.write(prefix + "\n")
    except FileExistsError:
        tries = 1
        while tries < 10:
            with open(filename) as f:
                prefix = f.readline()[:-1]
            if len(prefix) == 33:
                break
            tries += 1
            prefix = ""
            time.sleep(0.5)

    if not prefix:
        print("Could not read remote cache key prefix file")
        sys.exit(1)

    return prefix


KEY_PREFIX: str = get_or_create_key_prefix()


def bounce_key_prefix_for_testing(test_name: str) -> None:
    global KEY_PREFIX
    KEY_PREFIX = test_name + ":" + str(os.getpid()) + ":"
    # We are taking the hash of the KEY_PREFIX to decrease the size of the key.
    # Memcached keys should have a length of less than 250.
    KEY_PREFIX = hashlib.sha1(KEY_PREFIX.encode()).hexdigest() + ":"


def get_cache_backend(cache_name: Optional[str]) -> BaseCache:
    if cache_name is None:
        cache_name = "default"
    return caches[cache_name]


def cache_with_key(
    keyfunc: Callable[ParamT, str],
    cache_name: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Callable[[Callable[ParamT, ReturnT]], Callable[ParamT, ReturnT]]:
    """Decorator which applies Django caching to a function.

    Decorator argument is a function which computes a cache key
    from the original function's arguments.  You are responsible
    for avoiding collisions with other uses of this decorator or
    other uses of caching."""

    def decorator(func: Callable[ParamT, ReturnT]) -> Callable[ParamT, ReturnT]:
        @wraps(func)
        def func_with_caching(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ReturnT:
            key = keyfunc(*args, **kwargs)

            try:
                val = cache_get(key, cache_name=cache_name)
            except InvalidCacheKeyError:
                stack_trace = traceback.format_exc()
                log_invalid_cache_keys(stack_trace, [key])
                return func(*args, **kwargs)

            # Values are singleton tuples so that we can distinguish
            # a result of None from a missing key.
            if val is not None:
                return val[0]

            val = func(*args, **kwargs)
            if isinstance(val, QuerySetAny):
                logging.error(
                    "cache_with_key attempted to store a full QuerySet object -- declining to cache",
                    stack_info=True,
                )
            else:
                cache_set(key, val, cache_name=cache_name, timeout=timeout)

            return val

        return func_with_caching

    return decorator


class InvalidCacheKeyError(Exception):
    pass


def log_invalid_cache_keys(stack_trace: str, key: List[str]) -> None:
    logger.warning(
        "Invalid cache key used: %s\nStack trace: %s\n",
        key,
        stack_trace,
    )


def validate_cache_key(key: str) -> None:
    if not key.startswith(KEY_PREFIX):
        key = KEY_PREFIX + key

    # Theoretically memcached can handle non-ascii characters
    # and only "control" characters are strictly disallowed, see:
    # https://github.com/memcached/memcached/blob/master/doc/protocol.txt
    # However, limiting the characters we allow in keys simiplifies things,
    # and anyway we use a hash function when forming some keys to ensure
    # the resulting keys fit the regex below.
    # The regex checks "all characters between ! and ~ in the ascii table",
    # which happens to be the set of all "nice" ascii characters.
    if not bool(re.fullmatch(r"([!-~])+", key)):
        raise InvalidCacheKeyError("Invalid characters in the cache key: " + key)
    if len(key) > MEMCACHED_MAX_KEY_LENGTH:
        raise InvalidCacheKeyError(f"Cache key too long: {key} Length: {len(key)}")


def cache_set(
    key: str, val: Any, cache_name: Optional[str] = None, timeout: Optional[int] = None
) -> None:
    final_key = KEY_PREFIX + key
    validate_cache_key(final_key)

    remote_cache_stats_start()
    cache_backend = get_cache_backend(cache_name)
    cache_backend.set(final_key, (val,), timeout=timeout)
    remote_cache_stats_finish()


def cache_get(key: str, cache_name: Optional[str] = None) -> Any:
    final_key = KEY_PREFIX + key
    validate_cache_key(final_key)

    remote_cache_stats_start()
    cache_backend = get_cache_backend(cache_name)
    ret = cache_backend.get(final_key)
    remote_cache_stats_finish()
    return ret


def cache_get_many(keys: List[str], cache_name: Optional[str] = None) -> Dict[str, Any]:
    keys = [KEY_PREFIX + key for key in keys]
    for key in keys:
        validate_cache_key(key)
    remote_cache_stats_start()
    ret = get_cache_backend(cache_name).get_many(keys)
    remote_cache_stats_finish()
    return {key[len(KEY_PREFIX) :]: value for key, value in ret.items()}


def safe_cache_get_many(keys: List[str], cache_name: Optional[str] = None) -> Dict[str, Any]:
    """Variant of cache_get_many that drops any keys that fail
    validation, rather than throwing an exception visible to the
    caller."""
    try:
        # Almost always the keys will all be correct, so we just try
        # to do normal cache_get_many to avoid the overhead of
        # validating all the keys here.
        return cache_get_many(keys, cache_name)
    except InvalidCacheKeyError:
        stack_trace = traceback.format_exc()
        good_keys, bad_keys = filter_good_and_bad_keys(keys)

        log_invalid_cache_keys(stack_trace, bad_keys)
        return cache_get_many(good_keys, cache_name)


def cache_set_many(
    items: Dict[str, Any], cache_name: Optional[str] = None, timeout: Optional[int] = None
) -> None:
    new_items = {}
    for key in items:
        new_key = KEY_PREFIX + key
        validate_cache_key(new_key)
        new_items[new_key] = items[key]
    items = new_items
    remote_cache_stats_start()
    get_cache_backend(cache_name).set_many(items, timeout=timeout)
    remote_cache_stats_finish()


def safe_cache_set_many(
    items: Dict[str, Any], cache_name: Optional[str] = None, timeout: Optional[int] = None
) -> None:
    """Variant of cache_set_many that drops saving any keys that fail
    validation, rather than throwing an exception visible to the
    caller."""
    try:
        # Almost always the keys will all be correct, so we just try
        # to do normal cache_set_many to avoid the overhead of
        # validating all the keys here.
        return cache_set_many(items, cache_name, timeout)
    except InvalidCacheKeyError:
        stack_trace = traceback.format_exc()

        good_keys, bad_keys = filter_good_and_bad_keys(list(items.keys()))
        log_invalid_cache_keys(stack_trace, bad_keys)

        good_items = {key: items[key] for key in good_keys}
        return cache_set_many(good_items, cache_name, timeout)


def cache_delete(key: str, cache_name: Optional[str] = None) -> None:
    final_key = KEY_PREFIX + key
    validate_cache_key(final_key)

    remote_cache_stats_start()
    get_cache_backend(cache_name).delete(final_key)
    remote_cache_stats_finish()


def cache_delete_many(items: Iterable[str], cache_name: Optional[str] = None) -> None:
    keys = [KEY_PREFIX + item for item in items]
    for key in keys:
        validate_cache_key(key)
    remote_cache_stats_start()
    get_cache_backend(cache_name).delete_many(keys)
    remote_cache_stats_finish()


def filter_good_and_bad_keys(keys: List[str]) -> Tuple[List[str], List[str]]:
    good_keys = []
    bad_keys = []
    for key in keys:
        try:
            validate_cache_key(key)
            good_keys.append(key)
        except InvalidCacheKeyError:
            bad_keys.append(key)

    return good_keys, bad_keys


# Generic_bulk_cached fetch and its helpers.  We start with declaring
# a few type variables that help define its interface.

# Type for the cache's keys; will typically be int or str.
ObjKT = TypeVar("ObjKT")

# Type for items to be fetched from the database (e.g. a Django model object)
ItemT = TypeVar("ItemT")

# Type for items to be stored in the cache (e.g. a dictionary serialization).
# Will equal ItemT unless a cache_transformer is specified.
CacheItemT = TypeVar("CacheItemT")

# Type for compressed items for storage in the cache.  For
# serializable objects, will be the object; if encoded, bytes.
CompressedItemT = TypeVar("CompressedItemT")


# Required arguments are as follows:
# * object_ids: The list of object ids to look up
# * cache_key_function: object_id => cache key
# * query_function: [object_ids] => [objects from database]
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
    query_function: Callable[[List[ObjKT]], Iterable[ItemT]],
    object_ids: Sequence[ObjKT],
    *,
    extractor: Callable[[CompressedItemT], CacheItemT],
    setter: Callable[[CacheItemT], CompressedItemT],
    id_fetcher: Callable[[ItemT], ObjKT],
    cache_transformer: Callable[[ItemT], CacheItemT],
) -> Dict[ObjKT, CacheItemT]:
    if len(object_ids) == 0:
        # Nothing to fetch.
        return {}

    cache_keys: Dict[ObjKT, str] = {}
    for object_id in object_ids:
        cache_keys[object_id] = cache_key_function(object_id)

    cached_objects_compressed: Dict[str, Tuple[CompressedItemT]] = safe_cache_get_many(
        [cache_keys[object_id] for object_id in object_ids],
    )

    cached_objects = {key: extractor(val[0]) for key, val in cached_objects_compressed.items()}
    needed_ids = [
        object_id for object_id in object_ids if cache_keys[object_id] not in cached_objects
    ]

    # Only call query_function if there are some ids to fetch from the database:
    if len(needed_ids) > 0:
        db_objects = query_function(needed_ids)
    else:
        db_objects = []

    items_for_remote_cache: Dict[str, Tuple[CompressedItemT]] = {}
    for obj in db_objects:
        key = cache_keys[id_fetcher(obj)]
        item = cache_transformer(obj)
        items_for_remote_cache[key] = (setter(item),)
        cached_objects[key] = item
    if len(items_for_remote_cache) > 0:
        safe_cache_set_many(items_for_remote_cache)
    return {
        object_id: cached_objects[cache_keys[object_id]]
        for object_id in object_ids
        if cache_keys[object_id] in cached_objects
    }


def bulk_cached_fetch(
    cache_key_function: Callable[[ObjKT], str],
    query_function: Callable[[List[ObjKT]], Iterable[ItemT]],
    object_ids: Sequence[ObjKT],
    *,
    id_fetcher: Callable[[ItemT], ObjKT],
) -> Dict[ObjKT, ItemT]:
    return generic_bulk_cached_fetch(
        cache_key_function,
        query_function,
        object_ids,
        id_fetcher=id_fetcher,
        extractor=lambda obj: obj,
        setter=lambda obj: obj,
        cache_transformer=lambda obj: obj,
    )


def preview_url_cache_key(url: str) -> str:
    return f"preview_url:{hashlib.sha1(url.encode()).hexdigest()}"


def display_recipient_cache_key(recipient_id: int) -> str:
    return f"display_recipient_dict:{recipient_id}"


def single_user_display_recipient_cache_key(user_id: int) -> str:
    return f"single_user_display_recipient:{user_id}"


def user_profile_cache_key_id(email: str, realm_id: int) -> str:
    return f"user_profile:{hashlib.sha1(email.strip().encode()).hexdigest()}:{realm_id}"


def user_profile_cache_key(email: str, realm: "Realm") -> str:
    return user_profile_cache_key_id(email, realm.id)


def user_profile_delivery_email_cache_key(delivery_email: str, realm_id: int) -> str:
    return f"user_profile_by_delivery_email:{hashlib.sha1(delivery_email.strip().encode()).hexdigest()}:{realm_id}"


def bot_profile_cache_key(email: str, realm_id: int) -> str:
    return f"bot_profile:{hashlib.sha1(email.strip().encode()).hexdigest()}"


def user_profile_by_id_cache_key(user_profile_id: int) -> str:
    return f"user_profile_by_id:{user_profile_id}"


def user_profile_by_api_key_cache_key(api_key: str) -> str:
    return f"user_profile_by_api_key:{api_key}"


def get_cross_realm_dicts_key() -> str:
    emails = list(settings.CROSS_REALM_BOT_EMAILS)
    raw_key = ",".join(sorted(emails))
    digest = hashlib.sha1(raw_key.encode()).hexdigest()
    return f"get_cross_realm_dicts:{digest}"


realm_user_dict_fields: List[str] = [
    "id",
    "full_name",
    "email",
    "avatar_source",
    "avatar_version",
    "is_active",
    "role",
    "is_billing_admin",
    "is_bot",
    "timezone",
    "date_joined",
    "bot_owner_id",
    "delivery_email",
    "bot_type",
    "long_term_idle",
    "email_address_visibility",
]


def realm_user_dicts_cache_key(realm_id: int) -> str:
    return f"realm_user_dicts:{realm_id}"


def get_muting_users_cache_key(muted_user_id: int) -> str:
    return f"muting_users_list:{muted_user_id}"


def get_realm_used_upload_space_cache_key(realm_id: int) -> str:
    return f"realm_used_upload_space:{realm_id}"


def get_realm_seat_count_cache_key(realm_id: int) -> str:
    return f"realm_seat_count:{realm_id}"


def active_user_ids_cache_key(realm_id: int) -> str:
    return f"active_user_ids:{realm_id}"


def active_non_guest_user_ids_cache_key(realm_id: int) -> str:
    return f"active_non_guest_user_ids:{realm_id}"


bot_dict_fields: List[str] = [
    "api_key",
    "avatar_source",
    "avatar_version",
    "bot_owner_id",
    "bot_type",
    "default_all_public_streams",
    "default_events_register_stream__name",
    "default_sending_stream__name",
    "email",
    "full_name",
    "id",
    "is_active",
    "realm_id",
]


def bot_dicts_in_realm_cache_key(realm_id: int) -> str:
    return f"bot_dicts_in_realm:{realm_id}"


def delete_user_profile_caches(user_profiles: Iterable["UserProfile"], realm_id: int) -> None:
    # Imported here to avoid cyclic dependency.
    from zerver.lib.users import get_all_api_keys
    from zerver.models.users import is_cross_realm_bot_email

    keys = []
    for user_profile in user_profiles:
        keys.append(user_profile_by_id_cache_key(user_profile.id))
        keys += map(user_profile_by_api_key_cache_key, get_all_api_keys(user_profile))
        keys.append(user_profile_cache_key_id(user_profile.email, realm_id))
        keys.append(user_profile_delivery_email_cache_key(user_profile.delivery_email, realm_id))
        if user_profile.is_bot and is_cross_realm_bot_email(user_profile.email):
            # Handle clearing system bots from their special cache.
            keys.append(bot_profile_cache_key(user_profile.email, realm_id))
            keys.append(get_cross_realm_dicts_key())

    cache_delete_many(keys)


def delete_display_recipient_cache(user_profile: "UserProfile") -> None:
    from zerver.models import Subscription  # We need to import here to avoid cyclic dependency.

    recipient_ids = Subscription.objects.filter(user_profile=user_profile).values_list(
        "recipient_id", flat=True
    )
    keys = [display_recipient_cache_key(rid) for rid in recipient_ids]
    keys.append(single_user_display_recipient_cache_key(user_profile.id))
    cache_delete_many(keys)


def changed(update_fields: Optional[Sequence[str]], fields: List[str]) -> bool:
    if update_fields is None:
        # adds/deletes should invalidate the cache
        return True

    update_fields_set = set(update_fields)
    return any(f in update_fields_set for f in fields)


# Called by models/users.py to flush the user_profile cache whenever we save
# a user_profile object
def flush_user_profile(
    *,
    instance: "UserProfile",
    update_fields: Optional[Sequence[str]] = None,
    **kwargs: object,
) -> None:
    user_profile = instance
    delete_user_profile_caches([user_profile], user_profile.realm_id)

    # Invalidate our active_users_in_realm info dict if any user has changed
    # the fields in the dict or become (in)active
    if changed(update_fields, realm_user_dict_fields):
        cache_delete(realm_user_dicts_cache_key(user_profile.realm_id))

    if changed(update_fields, ["is_active"]):
        cache_delete(active_user_ids_cache_key(user_profile.realm_id))
        cache_delete(active_non_guest_user_ids_cache_key(user_profile.realm_id))

    if changed(update_fields, ["role"]):
        cache_delete(active_non_guest_user_ids_cache_key(user_profile.realm_id))

    if changed(update_fields, ["email", "full_name", "id", "is_mirror_dummy"]):
        delete_display_recipient_cache(user_profile)

    # Invalidate our bots_in_realm info dict if any bot has
    # changed the fields in the dict or become (in)active
    if user_profile.is_bot and changed(update_fields, bot_dict_fields):
        cache_delete(bot_dicts_in_realm_cache_key(user_profile.realm_id))


def flush_muting_users_cache(*, instance: "MutedUser", **kwargs: object) -> None:
    mute_object = instance
    cache_delete(get_muting_users_cache_key(mute_object.muted_user_id))


# Called by models/realms.py to flush various caches whenever we save
# a Realm object.  The main tricky thing here is that Realm info is
# generally cached indirectly through user_profile objects.
def flush_realm(
    *,
    instance: "Realm",
    update_fields: Optional[Sequence[str]] = None,
    from_deletion: bool = False,
    **kwargs: object,
) -> None:
    realm = instance
    users = realm.get_active_users()
    delete_user_profile_caches(users, realm.id)

    if (
        from_deletion
        or realm.deactivated
        or (update_fields is not None and "string_id" in update_fields)
    ):
        cache_delete(realm_user_dicts_cache_key(realm.id))
        cache_delete(active_user_ids_cache_key(realm.id))
        cache_delete(bot_dicts_in_realm_cache_key(realm.id))
        cache_delete(realm_alert_words_cache_key(realm.id))
        cache_delete(realm_alert_words_automaton_cache_key(realm.id))
        cache_delete(active_non_guest_user_ids_cache_key(realm.id))
        cache_delete(realm_rendered_description_cache_key(realm))
        cache_delete(realm_text_description_cache_key(realm))
    elif changed(update_fields, ["description"]):
        cache_delete(realm_rendered_description_cache_key(realm))
        cache_delete(realm_text_description_cache_key(realm))


def realm_alert_words_cache_key(realm_id: int) -> str:
    return f"realm_alert_words:{realm_id}"


def realm_alert_words_automaton_cache_key(realm_id: int) -> str:
    return f"realm_alert_words_automaton:{realm_id}"


def realm_rendered_description_cache_key(realm: "Realm") -> str:
    return f"realm_rendered_description:{realm.string_id}"


def realm_text_description_cache_key(realm: "Realm") -> str:
    return f"realm_text_description:{realm.string_id}"


# Called by models/streams.py to flush the stream cache whenever we save a stream
# object.
def flush_stream(
    *,
    instance: "Stream",
    update_fields: Optional[Sequence[str]] = None,
    **kwargs: object,
) -> None:
    from zerver.models import UserProfile

    stream = instance

    if update_fields is None or (
        "name" in update_fields
        and UserProfile.objects.filter(
            Q(default_sending_stream=stream) | Q(default_events_register_stream=stream)
        ).exists()
    ):
        cache_delete(bot_dicts_in_realm_cache_key(stream.realm_id))


def flush_used_upload_space_cache(
    *,
    instance: "Attachment",
    created: bool = True,
    **kwargs: object,
) -> None:
    attachment = instance

    if created:
        cache_delete(get_realm_used_upload_space_cache_key(attachment.owner.realm_id))


def to_dict_cache_key_id(message_id: int) -> str:
    return f"message_dict:{message_id}"


def to_dict_cache_key(message: "Message", realm_id: Optional[int] = None) -> str:
    return to_dict_cache_key_id(message.id)


def open_graph_description_cache_key(content: bytes, request_url: str) -> str:
    return f"open_graph_description_path:{hashlib.sha1(request_url.encode()).hexdigest()}"


def flush_message(*, instance: "Message", **kwargs: object) -> None:
    message = instance
    cache_delete(to_dict_cache_key_id(message.id))


def flush_submessage(*, instance: "SubMessage", **kwargs: object) -> None:
    submessage = instance
    # submessages are not cached directly, they are part of their
    # parent messages
    message_id = submessage.message_id
    cache_delete(to_dict_cache_key_id(message_id))


class IgnoreUnhashableLruCacheWrapper(Generic[ParamT, ReturnT]):
    def __init__(
        self, function: Callable[ParamT, ReturnT], cached_function: "_lru_cache_wrapper[ReturnT]"
    ) -> None:
        self.key_prefix = KEY_PREFIX
        self.function = function
        self.cached_function = cached_function
        self.cache_info = cached_function.cache_info
        self.cache_clear = cached_function.cache_clear

    def __call__(self, *args: ParamT.args, **kwargs: ParamT.kwargs) -> ReturnT:
        if settings.DEVELOPMENT and not settings.TEST_SUITE:  # nocoverage
            # In the development environment, we want every file
            # change to refresh the source files from disk.
            return self.function(*args, **kwargs)

        if self.key_prefix != KEY_PREFIX:
            # Clear cache when cache.KEY_PREFIX changes. This is used in
            # tests.
            self.cache_clear()
            self.key_prefix = KEY_PREFIX

        try:
            return self.cached_function(
                *args,
                **kwargs,  # type: ignore[arg-type] # might be unhashable
            )
        except TypeError:
            # args or kwargs contains an element which is unhashable. In
            # this case we don't cache the result.
            pass

        # Deliberately calling this function from outside of exception
        # handler to get a more descriptive traceback. Otherwise traceback
        # can include the exception from cached_function as well.
        return self.function(*args, **kwargs)


def ignore_unhashable_lru_cache(
    maxsize: int = 128, typed: bool = False
) -> Callable[[Callable[ParamT, ReturnT]], IgnoreUnhashableLruCacheWrapper[ParamT, ReturnT]]:
    """
    This is a wrapper over lru_cache function. It adds following features on
    top of lru_cache:

        * It will not cache result of functions with unhashable arguments.
        * It will clear cache whenever zerver.lib.cache.KEY_PREFIX changes.
    """
    internal_decorator = lru_cache(maxsize=maxsize, typed=typed)

    def decorator(
        user_function: Callable[ParamT, ReturnT],
    ) -> IgnoreUnhashableLruCacheWrapper[ParamT, ReturnT]:
        return IgnoreUnhashableLruCacheWrapper(user_function, internal_decorator(user_function))

    return decorator


def dict_to_items_tuple(user_function: Callable[..., Any]) -> Callable[..., Any]:
    """Wrapper that converts any dict args to dict item tuples."""

    def dict_to_tuple(arg: Any) -> Any:
        if isinstance(arg, dict):
            return tuple(sorted(arg.items()))
        return arg

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        new_args = (dict_to_tuple(arg) for arg in args)
        return user_function(*new_args, **kwargs)

    return wrapper


def items_tuple_to_dict(user_function: Callable[..., Any]) -> Callable[..., Any]:
    """Wrapper that converts any dict items tuple args to dicts."""

    def dict_items_to_dict(arg: Any) -> Any:
        if isinstance(arg, tuple):
            try:
                return dict(arg)
            except TypeError:
                pass
        return arg

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        new_args = (dict_items_to_dict(arg) for arg in args)
        new_kwargs = {key: dict_items_to_dict(val) for key, val in kwargs.items()}
        return user_function(*new_args, **new_kwargs)

    return wrapper

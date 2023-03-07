# See https://zulip.readthedocs.io/en/latest/subsystems/caching.html for docs
import datetime
import logging
from typing import Any, Callable, Dict, Iterable, Tuple

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db.models import QuerySet
from django.utils.timezone import now as timezone_now
from django_stubs_ext import ValuesQuerySet

# This file needs to be different from cache.py because cache.py
# cannot import anything from zerver.models or we'd have an import
# loop
from analytics.models import RealmCount
from zerver.lib.cache import (
    cache_set_many,
    get_remote_cache_requests,
    get_remote_cache_time,
    get_stream_cache_key,
    user_profile_by_api_key_cache_key,
    user_profile_cache_key,
)
from zerver.lib.safe_session_cached_db import SessionStore
from zerver.lib.sessions import session_engine
from zerver.lib.users import get_all_api_keys
from zerver.models import (
    Client,
    Huddle,
    Stream,
    UserProfile,
    get_client_cache_key,
    huddle_hash_cache_key,
)


def user_cache_items(
    items_for_remote_cache: Dict[str, Tuple[UserProfile]], user_profile: UserProfile
) -> None:
    for api_key in get_all_api_keys(user_profile):
        items_for_remote_cache[user_profile_by_api_key_cache_key(api_key)] = (user_profile,)
    items_for_remote_cache[user_profile_cache_key(user_profile.email, user_profile.realm)] = (
        user_profile,
    )
    # We have other user_profile caches, but none of them are on the
    # core serving path for lots of requests.


def stream_cache_items(items_for_remote_cache: Dict[str, Tuple[Stream]], stream: Stream) -> None:
    items_for_remote_cache[get_stream_cache_key(stream.name, stream.realm_id)] = (stream,)


def client_cache_items(items_for_remote_cache: Dict[str, Tuple[Client]], client: Client) -> None:
    items_for_remote_cache[get_client_cache_key(client.name)] = (client,)


def huddle_cache_items(items_for_remote_cache: Dict[str, Tuple[Huddle]], huddle: Huddle) -> None:
    items_for_remote_cache[huddle_hash_cache_key(huddle.huddle_hash)] = (huddle,)


def session_cache_items(
    items_for_remote_cache: Dict[str, Dict[str, object]], session: Session
) -> None:
    if settings.SESSION_ENGINE != "zerver.lib.safe_session_cached_db":
        # If we're not using the cached_db session engine, we there
        # will be no store.cache_key attribute, and in any case we
        # don't need to fill the cache, since it won't exist.
        return
    store = session_engine.SessionStore(session_key=session.session_key)
    assert isinstance(store, SessionStore)
    items_for_remote_cache[store.cache_key] = store.decode(session.session_data)


def get_active_realm_ids() -> ValuesQuerySet[RealmCount, int]:
    """For installations like Zulip Cloud hosting a lot of realms, it only makes
    sense to do cache-filling work for realms that have any currently
    active users/clients.  Otherwise, we end up with every single-user
    trial organization that has ever been created costing us N streams
    worth of cache work (where N is the number of default streams for
    a new organization).
    """
    date = timezone_now() - datetime.timedelta(days=2)
    return (
        RealmCount.objects.filter(end_time__gte=date, property="1day_actives::day", value__gt=0)
        .distinct("realm_id")
        .values_list("realm_id", flat=True)
    )


def get_streams() -> QuerySet[Stream]:
    return (
        Stream.objects.select_related()
        .filter(realm__in=get_active_realm_ids())
        .exclude(
            # We filter out Zephyr realms, because they can easily
            # have 10,000s of streams with only 1 subscriber.
            is_in_zephyr_realm=True
        )
    )


def get_users() -> QuerySet[UserProfile]:
    return UserProfile.objects.select_related().filter(
        long_term_idle=False, realm__in=get_active_realm_ids()
    )


# Format is (objects query, items filler function, timeout, batch size)
#
# The objects queries are put inside lambdas to prevent Django from
# doing any setup for things we're unlikely to use (without the lambda
# wrapper the below adds an extra 3ms or so to startup time for
# anything importing this file).
cache_fillers: Dict[
    str, Tuple[Callable[[], Iterable[Any]], Callable[[Dict[str, Any], Any], None], int, int]
] = {
    "user": (get_users, user_cache_items, 3600 * 24 * 7, 10000),
    "client": (
        lambda: Client.objects.select_related().all(),
        client_cache_items,
        3600 * 24 * 7,
        10000,
    ),
    "stream": (get_streams, stream_cache_items, 3600 * 24 * 7, 10000),
    "huddle": (
        lambda: Huddle.objects.select_related().all(),
        huddle_cache_items,
        3600 * 24 * 7,
        10000,
    ),
    "session": (lambda: Session.objects.all(), session_cache_items, 3600 * 24 * 7, 10000),
}


def fill_remote_cache(cache: str) -> None:
    remote_cache_time_start = get_remote_cache_time()
    remote_cache_requests_start = get_remote_cache_requests()
    items_for_remote_cache: Dict[str, Any] = {}
    (objects, items_filler, timeout, batch_size) = cache_fillers[cache]
    count = 0
    for obj in objects():
        items_filler(items_for_remote_cache, obj)
        count += 1
        if count % batch_size == 0:
            cache_set_many(items_for_remote_cache, timeout=3600 * 24)
            items_for_remote_cache = {}
    cache_set_many(items_for_remote_cache, timeout=3600 * 24 * 7)
    logging.info(
        "Successfully populated %s cache!  Consumed %s remote cache queries (%s time)",
        cache,
        get_remote_cache_requests() - remote_cache_requests_start,
        round(get_remote_cache_time() - remote_cache_time_start, 2),
    )

# See https://zulip.readthedocs.io/en/latest/subsystems/caching.html for docs
import logging
from collections.abc import Callable, Iterable
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import connection
from django.db.models import QuerySet
from django.utils.timezone import now as timezone_now

# This file needs to be different from cache.py because cache.py
# cannot import anything from zerver.models or we'd have an import
# loop
from analytics.models import RealmCount
from zerver.lib.cache import (
    cache_set_many,
    get_remote_cache_requests,
    get_remote_cache_time,
    user_profile_narrow_by_id_cache_key,
)
from zerver.lib.safe_session_cached_db import SessionStore
from zerver.lib.sessions import session_engine
from zerver.models import Client, UserProfile
from zerver.models.clients import get_client_cache_key
from zerver.models.users import base_get_user_narrow_queryset


def get_narrow_users() -> QuerySet[UserProfile]:
    return base_get_user_narrow_queryset().filter(
        long_term_idle=False, realm__in=get_active_realm_ids()
    )


def user_narrow_cache_items(
    items_for_remote_cache: dict[str, tuple[UserProfile]], user_profile: UserProfile
) -> None:
    items_for_remote_cache[user_profile_narrow_by_id_cache_key(user_profile.id)] = (user_profile,)


def client_cache_items(items_for_remote_cache: dict[str, tuple[Client]], client: Client) -> None:
    items_for_remote_cache[get_client_cache_key(client.name)] = (client,)


def session_cache_items(
    items_for_remote_cache: dict[str, dict[str, object]], session: Session
) -> None:
    if settings.SESSION_ENGINE != "zerver.lib.safe_session_cached_db":
        # If we're not using the cached_db session engine, we there
        # will be no store.cache_key attribute, and in any case we
        # don't need to fill the cache, since it won't exist.
        return
    store = session_engine.SessionStore(session_key=session.session_key)
    assert isinstance(store, SessionStore)
    items_for_remote_cache[store.cache_key] = store.decode(session.session_data)


def get_active_realm_ids() -> QuerySet[RealmCount, int]:
    """For installations like Zulip Cloud hosting a lot of realms, it only makes
    sense to do cache-filling work for realms that have any currently
    active users/clients.  Otherwise, we end up with every single-user
    trial organization that has ever been created costing us N streams
    worth of cache work (where N is the number of default streams for
    a new organization).
    """
    date = timezone_now() - timedelta(days=2)
    return (
        RealmCount.objects.filter(
            end_time__gte=date,
            property="1day_actives::day",
            # Filtering on subgroup is important to ensure we use the good indexes.
            subgroup=None,
            value__gt=0,
        )
        .distinct("realm_id")
        .values_list("realm_id", flat=True)
    )


# Format is (objects query, items filler function, timeout, batch size)
#
# The objects queries are put inside lambdas to prevent Django from
# doing any setup for things we're unlikely to use (without the lambda
# wrapper the below adds an extra 3ms or so to startup time for
# anything importing this file).
cache_fillers: dict[
    str, tuple[Callable[[], Iterable[Any]], Callable[[dict[str, Any], Any], None], int, int]
] = {
    "user_narrow": (get_narrow_users, user_narrow_cache_items, 3600 * 24 * 7, 10000),
    "client": (
        Client.objects.all,
        client_cache_items,
        3600 * 24 * 7,
        10000,
    ),
    "session": (Session.objects.all, session_cache_items, 3600 * 24 * 7, 10000),
}


class SQLQueryCounter:
    def __init__(self) -> None:
        self.count = 0

    def __call__(
        self,
        execute: Callable[[str, Any, bool, dict[str, Any]], Any],
        sql: str,
        params: Any,
        many: bool,
        context: dict[str, Any],
    ) -> Any:
        self.count += 1
        return execute(sql, params, many, context)


def fill_remote_cache(cache: str) -> None:
    remote_cache_time_start = get_remote_cache_time()
    remote_cache_requests_start = get_remote_cache_requests()
    items_for_remote_cache: dict[str, Any] = {}
    (objects, items_filler, timeout, batch_size) = cache_fillers[cache]
    count = 0
    db_query_counter = SQLQueryCounter()
    with connection.execute_wrapper(db_query_counter):
        for obj in objects():
            items_filler(items_for_remote_cache, obj)
            count += 1
            if count % batch_size == 0:
                cache_set_many(items_for_remote_cache, timeout=timeout)
                items_for_remote_cache = {}
        cache_set_many(items_for_remote_cache, timeout=timeout)
    logging.info(
        "Successfully populated %s cache: %d items, %d DB queries, %d memcached sets, %.2f seconds",
        cache,
        count,
        db_query_counter.count,
        get_remote_cache_requests() - remote_cache_requests_start,
        get_remote_cache_time() - remote_cache_time_start,
    )

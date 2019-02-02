# See https://zulip.readthedocs.io/en/latest/subsystems/caching.html for docs

from typing import Any, Callable, Dict, List, Tuple

import datetime
import logging

# This file needs to be different from cache.py because cache.py
# cannot import anything from zerver.models or we'd have an import
# loop
from analytics.models import RealmCount
from django.conf import settings
from zerver.models import Message, UserProfile, Stream, get_stream_cache_key, \
    Recipient, get_recipient_cache_key, Client, get_client_cache_key, \
    Huddle, huddle_hash_cache_key
from zerver.lib.cache import \
    user_profile_by_api_key_cache_key, \
    user_profile_cache_key, get_remote_cache_time, get_remote_cache_requests, \
    cache_set_many, to_dict_cache_key_id
from zerver.lib.message import MessageDict
from zerver.lib.users import get_all_api_keys
from importlib import import_module
from django.contrib.sessions.models import Session
from django.db.models import Q
from django.utils.timezone import now as timezone_now

MESSAGE_CACHE_SIZE = 75000

def message_fetch_objects() -> List[Any]:
    try:
        max_id = Message.objects.only('id').order_by("-id")[0].id
    except IndexError:
        return []
    return Message.objects.select_related().filter(~Q(sender__email='tabbott/extra@mit.edu'),
                                                   id__gt=max_id - MESSAGE_CACHE_SIZE)

def message_cache_items(items_for_remote_cache: Dict[str, Tuple[bytes]],
                        message: Message) -> None:
    '''
    Note: this code is untested, and the caller has been
    commented out for a while.
    '''
    key = to_dict_cache_key_id(message.id)
    value = MessageDict.to_dict_uncached(message)
    items_for_remote_cache[key] = (value,)

def user_cache_items(items_for_remote_cache: Dict[str, Tuple[UserProfile]],
                     user_profile: UserProfile) -> None:
    for api_key in get_all_api_keys(user_profile):
        items_for_remote_cache[user_profile_by_api_key_cache_key(api_key)] = (user_profile,)
    items_for_remote_cache[user_profile_cache_key(user_profile.email,
                                                  user_profile.realm)] = (user_profile,)
    # We have other user_profile caches, but none of them are on the
    # core serving path for lots of requests.

def stream_cache_items(items_for_remote_cache: Dict[str, Tuple[Stream]],
                       stream: Stream) -> None:
    items_for_remote_cache[get_stream_cache_key(stream.name, stream.realm_id)] = (stream,)

def client_cache_items(items_for_remote_cache: Dict[str, Tuple[Client]],
                       client: Client) -> None:
    items_for_remote_cache[get_client_cache_key(client.name)] = (client,)

def huddle_cache_items(items_for_remote_cache: Dict[str, Tuple[Huddle]],
                       huddle: Huddle) -> None:
    items_for_remote_cache[huddle_hash_cache_key(huddle.huddle_hash)] = (huddle,)

def recipient_cache_items(items_for_remote_cache: Dict[str, Tuple[Recipient]],
                          recipient: Recipient) -> None:
    items_for_remote_cache[get_recipient_cache_key(recipient.type, recipient.type_id)] = (recipient,)

session_engine = import_module(settings.SESSION_ENGINE)
def session_cache_items(items_for_remote_cache: Dict[str, str],
                        session: Session) -> None:
    if settings.SESSION_ENGINE != "django.contrib.sessions.backends.cached_db":
        # If we're not using the cached_db session engine, we there
        # will be no store.cache_key attribute, and in any case we
        # don't need to fill the cache, since it won't exist.
        return
    store = session_engine.SessionStore(session_key=session.session_key)  # type: ignore # import_module
    items_for_remote_cache[store.cache_key] = store.decode(session.session_data)

def get_active_realm_ids() -> List[int]:
    """For servers like zulipchat.com with a lot of realms, it only makes
    sense to do cache-filling work for realms that have any currently
    active users/clients.  Otherwise, we end up with every single-user
    trial organization that has ever been created costing us N streams
    worth of cache work (where N is the number of default streams for
    a new organization).
    """
    date = timezone_now() - datetime.timedelta(days=2)
    return RealmCount.objects.filter(
        end_time__gte=date,
        property="1day_actives::day",
        value__gt=0).distinct("realm_id").values_list("realm_id", flat=True)

def get_streams() -> List[Stream]:
    return Stream.objects.select_related().filter(
        realm__in=get_active_realm_ids()).exclude(
            # We filter out Zephyr realms, because they can easily
            # have 10,000s of streams with only 1 subscriber.
            is_in_zephyr_realm=True)

def get_recipients() -> List[Recipient]:
    return Recipient.objects.select_related().filter(
        type_id__in=get_streams().values_list("id", flat=True))  # type: ignore  # Should be QuerySet above

def get_users() -> List[UserProfile]:
    return UserProfile.objects.select_related().filter(
        long_term_idle=False,
        realm__in=get_active_realm_ids())

# Format is (objects query, items filler function, timeout, batch size)
#
# The objects queries are put inside lambdas to prevent Django from
# doing any setup for things we're unlikely to use (without the lambda
# wrapper the below adds an extra 3ms or so to startup time for
# anything importing this file).
cache_fillers = {
    'user': (get_users, user_cache_items, 3600*24*7, 10000),
    'client': (lambda: Client.objects.select_related().all(), client_cache_items, 3600*24*7, 10000),
    'recipient': (get_recipients, recipient_cache_items, 3600*24*7, 10000),
    'stream': (get_streams, stream_cache_items, 3600*24*7, 10000),
    # Message cache fetching disabled until we can fix the fact that it
    # does a bunch of inefficient memcached queries as part of filling
    # the display_recipient cache
    #    'message': (message_fetch_objects, message_cache_items, 3600 * 24, 1000),
    'huddle': (lambda: Huddle.objects.select_related().all(), huddle_cache_items, 3600*24*7, 10000),
    'session': (lambda: Session.objects.all(), session_cache_items, 3600*24*7, 10000),
}  # type: Dict[str, Tuple[Callable[[], List[Any]], Callable[[Dict[str, Any], Any], None], int, int]]

def fill_remote_cache(cache: str) -> None:
    remote_cache_time_start = get_remote_cache_time()
    remote_cache_requests_start = get_remote_cache_requests()
    items_for_remote_cache = {}  # type: Dict[str, Any]
    (objects, items_filler, timeout, batch_size) = cache_fillers[cache]
    count = 0
    for obj in objects():
        items_filler(items_for_remote_cache, obj)
        count += 1
        if (count % batch_size == 0):
            cache_set_many(items_for_remote_cache, timeout=3600*24)
            items_for_remote_cache = {}
    cache_set_many(items_for_remote_cache, timeout=3600*24*7)
    logging.info("Successfully populated %s cache!  Consumed %s remote cache queries (%s time)" %
                 (cache, get_remote_cache_requests() - remote_cache_requests_start,
                  round(get_remote_cache_time() - remote_cache_time_start, 2)))

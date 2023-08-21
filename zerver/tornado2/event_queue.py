# See https://zulip.readthedocs.io/en/latest/subsystems/events-system.html for
# high-level documentation on how this system works.
import copy
import logging
import os
import random
import time
import traceback
import uuid
from collections import deque
from contextlib import suppress
from functools import lru_cache
from typing import (
    AbstractSet,
    Any,
    Callable,
    Collection,
    Deque,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypedDict,
    Union,
    cast,
)

import orjson
import tornado.ioloop
from django.conf import settings
from django.utils.translation import gettext as _
from tornado import autoreload

from version import API_FEATURE_LEVEL, ZULIP_MERGE_BASE, ZULIP_VERSION
from zerver.lib.exceptions import JsonableError
from zerver.lib.queue import queue_json_publish, retry_event
from zerver.middleware import async_request_timer_restart
from .descriptors import clear_descriptor_by_handler_id, set_descriptor_by_handler_id
from .exceptions import BadEventQueueIdError
from .handlers import (
    clear_handler_by_id,
    finish_handler,
    get_handler_by_id,
    handler_stats_string,
)

# The idle timeout used to be a week, but we found that in that
# situation, queues from dead browser sessions would grow quite large
# due to the accumulation of message data in those queues.
DEFAULT_EVENT_QUEUE_TIMEOUT_SECS = 60 * 10
# We garbage-collect every minute; this is totally fine given that the
# GC scan takes ~2ms with 1000 event queues.
EVENT_QUEUE_GC_FREQ_MSECS = 1000 * 60 * 1

# Capped limit for how long a client can request an event queue
# to live
MAX_QUEUE_TIMEOUT_SECS = 7 * 24 * 60 * 60

# The heartbeats effectively act as a server-side timeout for
# get_events().  The actual timeout value is randomized for each
# client connection based on the below value.  We ensure that the
# maximum timeout value is 55 seconds, to deal with crappy home
# wireless routers that kill "inactive" http connections.
HEARTBEAT_MIN_FREQ_SECS = 45


def create_heartbeat_event() -> Dict[str, str]:
    return dict(type="heartbeat")


class ClientDescriptor:
    def __init__(
        self,
        user_profile_id: int,
        realm_id: int,
        event_queue: "EventQueue",
        client_type_name: str,
        lifespan_secs: int = 0,
    ) -> None:
        self.user_profile_id = user_profile_id
        self.realm_id = realm_id
        self.current_handler_id: Optional[int] = None
        self.current_client_name: Optional[str] = None
        self.event_queue = event_queue
        self.last_connection_time = time.time()
        self.client_type_name = client_type_name
        self._timeout_handle: Any = None  # TODO: should be return type of ioloop.call_later

        # Default for lifespan_secs is DEFAULT_EVENT_QUEUE_TIMEOUT_SECS;
        # but users can set it as high as MAX_QUEUE_TIMEOUT_SECS.
        if lifespan_secs == 0:
            lifespan_secs = DEFAULT_EVENT_QUEUE_TIMEOUT_SECS
        self.queue_timeout = min(lifespan_secs, MAX_QUEUE_TIMEOUT_SECS)

    def to_dict(self) -> Dict[str, Any]:
        # If you add a new key to this dict, make sure you add appropriate
        # migration code in from_dict or load_event_queues to account for
        # loading event queues that lack that key.
        return dict(
            user_profile_id=self.user_profile_id,
            realm_id=self.realm_id,
            event_queue=self.event_queue.to_dict(),
            queue_timeout=self.queue_timeout,
            last_connection_time=self.last_connection_time,
        )

    def __repr__(self) -> str:
        return f"ClientDescriptor<{self.event_queue.id}>"

    @classmethod
    def from_dict(cls, d: MutableMapping[str, Any]) -> "ClientDescriptor":
        if "client_type" in d:
            # Temporary migration for the rename of client_type to client_type_name
            d["client_type_name"] = d["client_type"]

        ret = cls(
            d["user_profile_id"],
            d["realm_id"],
            EventQueue.from_dict(d["event_queue"]),
            d["client_type_name"],
            d["queue_timeout"],
        )
        ret.last_connection_time = d["last_connection_time"]
        return ret

    def add_event(self, event: Mapping[str, Any]) -> None:
        if self.current_handler_id is not None:
            handler = get_handler_by_id(self.current_handler_id)
            assert handler._request is not None
            async_request_timer_restart(handler._request)

        self.event_queue.push(event)
        self.finish_current_handler()

    def finish_current_handler(self) -> bool:
        if self.current_handler_id is not None:
            try:
                finish_handler(
                    self.current_handler_id,
                    self.event_queue.id,
                    self.event_queue.contents(),
                )
            except Exception:
                logging.exception(
                    "Got error finishing handler for queue %s", self.event_queue.id, stack_info=True
                )
            finally:
                self.disconnect_handler()
            return True
        return False

    def accepts_event(self, event: Mapping[str, Any]) -> bool:
        # TODO: Allow some clients to opt out.
        assert event["type"] == "presence"
        return True

    def expired(self, now: float) -> bool:
        return (
            self.current_handler_id is None
            and now - self.last_connection_time >= self.queue_timeout
        )

    def connect_handler(self, handler_id: int, client_name: str) -> None:
        self.current_handler_id = handler_id
        self.current_client_name = client_name
        set_descriptor_by_handler_id(handler_id, self)
        self.last_connection_time = time.time()

        def timeout_callback() -> None:
            self._timeout_handle = None
            # All clients get heartbeat events
            heartbeat_event = create_heartbeat_event()
            self.add_event(heartbeat_event)

        ioloop = tornado.ioloop.IOLoop.current()
        interval = HEARTBEAT_MIN_FREQ_SECS + random.randint(0, 10)
        if self.client_type_name != "API: heartbeat test":
            self._timeout_handle = ioloop.call_later(interval, timeout_callback)

    def disconnect_handler(self, client_closed: bool = False) -> None:
        if self.current_handler_id:
            clear_descriptor_by_handler_id(self.current_handler_id)
            clear_handler_by_id(self.current_handler_id)
            if client_closed:
                logging.info(
                    "Client disconnected for queue %s (%s via %s)",
                    self.event_queue.id,
                    self.user_profile_id,
                    self.current_client_name,
                )
        self.current_handler_id = None
        self.current_client_name = None
        if self._timeout_handle is not None:
            ioloop = tornado.ioloop.IOLoop.current()
            ioloop.remove_timeout(self._timeout_handle)
            self._timeout_handle = None

    def cleanup(self) -> None:
        # Before we can GC the event queue, we need to disconnect the
        # handler and notify the client (or connection server) so that
        # they can clean up their own state related to the GC'd event
        # queue.  Finishing the handler before we GC ensures the
        # invariant that event queues are idle when passed to
        # `do_gc_event_queues` is preserved.
        self.finish_current_handler()
        do_gc_event_queues({self.event_queue.id}, {self.user_profile_id}, {self.realm_id})


class EventQueue:
    def __init__(self, id: str) -> None:
        # When extending this list of properties, one must be sure to
        # update to_dict and from_dict.

        self.queue: Deque[Dict[str, Any]] = deque()
        self.next_event_id: int = 0
        # will only be None for migration from old versions
        self.newest_pruned_id: Optional[int] = -1
        self.id: str = id

    def to_dict(self) -> Dict[str, Any]:
        # If you add a new key to this dict, make sure you add appropriate
        # migration code in from_dict or load_event_queues to account for
        # loading event queues that lack that key.
        d = dict(
            id=self.id,
            next_event_id=self.next_event_id,
            queue=list(self.queue),
        )
        if self.newest_pruned_id is not None:
            d["newest_pruned_id"] = self.newest_pruned_id
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EventQueue":
        ret = cls(d["id"])
        ret.next_event_id = d["next_event_id"]
        ret.newest_pruned_id = d.get("newest_pruned_id", None)
        ret.queue = deque(d["queue"])
        return ret

    def push(self, orig_event: Mapping[str, Any]) -> None:
        # By default, we make a shallow copy of the event dictionary
        # to push into the target event queue; this allows the calling
        # code to send the same "event" object to multiple queues.
        # This behavior is important because the event_queue system is
        # about to mutate the event dictionary, minimally to add the
        # event_id attribute.
        event = dict(orig_event)
        event["id"] = self.next_event_id
        self.next_event_id += 1
        self.queue.append(event)

    # Note that pop ignores virtual events.  This is fine in our
    # current usage since virtual events should always be resolved to
    # a real event before being given to users.
    def pop(self) -> Dict[str, Any]:
        return self.queue.popleft()

    def empty(self) -> bool:
        return len(self.queue) == 0

    # See the comment on pop; that applies here as well
    def prune(self, through_id: int) -> None:
        while len(self.queue) != 0 and self.queue[0]["id"] <= through_id:
            self.newest_pruned_id = self.queue[0]["id"]
            self.pop()

    def contents(self, include_internal_data: bool = False) -> List[Dict[str, Any]]:
        contents: List[Dict[str, Any]] = []

        for event in self.queue:
            contents.append(event)

        self.queue = deque(contents)

        return contents


# maps queue ids to client descriptors
clients: Dict[str, ClientDescriptor] = {}
# maps user id to list of client descriptors
user_clients: Dict[int, List[ClientDescriptor]] = {}

# list of registered gc hooks.
# each one will be called with a user profile id, queue, and bool
# last_for_client that is true if this is the last queue pertaining
# to this user_profile_id
# that is about to be deleted
gc_hooks: List[Callable[[int, ClientDescriptor, bool], None]] = []


def clear_client_event_queues_for_testing() -> None:
    assert settings.TEST_SUITE
    clients.clear()
    user_clients.clear()
    realm_clients_all_streams.clear()
    gc_hooks.clear()


def add_client_gc_hook(hook: Callable[[int, ClientDescriptor, bool], None]) -> None:
    gc_hooks.append(hook)


def access_client_descriptor(user_id: int, queue_id: str) -> ClientDescriptor:
    client = clients.get(queue_id)
    if client is not None:
        if user_id == client.user_profile_id:
            return client
        logging.warning(
            "User %d is not authorized for queue %s (%d via %s)",
            user_id,
            queue_id,
            client.user_profile_id,
            client.current_client_name,
        )
    raise BadEventQueueIdError(queue_id)


def get_client_descriptors_for_user(user_profile_id: int) -> List[ClientDescriptor]:
    return user_clients.get(user_profile_id, [])


def add_to_client_dicts(client: ClientDescriptor) -> None:
    user_clients.setdefault(client.user_profile_id, []).append(client)


def allocate_client_descriptor(new_queue_data: MutableMapping[str, Any]) -> ClientDescriptor:
    queue_id = str(uuid.uuid4())
    new_queue_data["event_queue"] = EventQueue(queue_id).to_dict()
    client = ClientDescriptor.from_dict(new_queue_data)
    clients[queue_id] = client
    add_to_client_dicts(client)
    return client


def do_gc_event_queues(
    to_remove: AbstractSet[str], affected_users: AbstractSet[int], affected_realms: AbstractSet[int]
) -> None:
    def filter_client_dict(
        client_dict: MutableMapping[int, List[ClientDescriptor]], key: int
    ) -> None:
        if key not in client_dict:
            return

        new_client_list = [c for c in client_dict[key] if c.event_queue.id not in to_remove]
        if len(new_client_list) == 0:
            del client_dict[key]
        else:
            client_dict[key] = new_client_list

    for user_id in affected_users:
        filter_client_dict(user_clients, user_id)

    for realm_id in affected_realms:
        filter_client_dict(realm_clients_all_streams, realm_id)

    for id in to_remove:
        for cb in gc_hooks:
            cb(
                clients[id].user_profile_id,
                clients[id],
                clients[id].user_profile_id not in user_clients,
            )
        del clients[id]


def gc_event_queues(port: int) -> None:
    start = time.time()
    to_remove: Set[str] = set()
    affected_users: Set[int] = set()
    affected_realms: Set[int] = set()
    for id, client in clients.items():
        if client.expired(start):
            to_remove.add(id)
            affected_users.add(client.user_profile_id)
            affected_realms.add(client.realm_id)

    # We don't need to call e.g. finish_current_handler on the clients
    # being removed because they are guaranteed to be idle (because
    # they are expired) and thus not have a current handler.
    do_gc_event_queues(to_remove, affected_users, affected_realms)

    if settings.PRODUCTION:
        logging.info(
            "Tornado %d removed %d expired event queues owned by %d users in %.3fs."
            "  Now %d active queues, %s",
            port,
            len(to_remove),
            len(affected_users),
            time.time() - start,
            len(clients),
            handler_stats_string(),
        )


def persistent_queue_filename(port: int, last: bool = False) -> str:
    if last:
        return settings.JSON_PERSISTENT_QUEUE_FILENAME_PATTERN % ("." + str(port) + ".last",)
    return settings.JSON_PERSISTENT_QUEUE_FILENAME_PATTERN % ("." + str(port),)


async def setup_event_queue(server: tornado.httpserver.HTTPServer, port: int) -> None:
    with suppress(OSError):
        os.rename(persistent_queue_filename(port), persistent_queue_filename(port, last=True))

    # Set up event queue garbage collection
    pc = tornado.ioloop.PeriodicCallback(lambda: gc_event_queues(port), EVENT_QUEUE_GC_FREQ_MSECS)
    pc.start()


def fetch_events(
    queue_id: Optional[str],
    dont_block: bool,
    last_event_id: Optional[int],
    user_profile_id: int,
    new_queue_data: Optional[MutableMapping[str, Any]],
    client_type_name: str,
    handler_id: int,
) -> Dict[str, Any]:
    try:
        was_connected = False
        orig_queue_id = queue_id
        extra_log_data = ""
        if queue_id is None:
            if dont_block:
                assert new_queue_data is not None
                client = allocate_client_descriptor(new_queue_data)
                queue_id = client.event_queue.id
            else:
                raise JsonableError(_("Missing 'queue_id' argument"))
        else:
            if last_event_id is None:
                raise JsonableError(_("Missing 'last_event_id' argument"))
            client = access_client_descriptor(user_profile_id, queue_id)
            if (
                client.event_queue.newest_pruned_id is not None
                and last_event_id < client.event_queue.newest_pruned_id
            ):
                raise JsonableError(
                    _("An event newer than {event_id} has already been pruned!").format(
                        event_id=last_event_id,
                    )
                )
            client.event_queue.prune(last_event_id)
            if (
                client.event_queue.newest_pruned_id is not None
                and last_event_id != client.event_queue.newest_pruned_id
            ):
                raise JsonableError(
                    _("Event {event_id} was not in this queue").format(
                        event_id=last_event_id,
                    )
                )
            was_connected = client.finish_current_handler()

        if not client.event_queue.empty() or dont_block:
            response: Dict[str, Any] = dict(
                events=client.event_queue.contents(),
            )
            if orig_queue_id is None:
                response["queue_id"] = queue_id
            if len(response["events"]) == 1:
                extra_log_data = "[{}/{}/{}]".format(
                    queue_id, len(response["events"]), response["events"][0]["type"]
                )
            else:
                extra_log_data = "[{}/{}]".format(queue_id, len(response["events"]))
            if was_connected:
                extra_log_data += " [was connected]"
            return dict(type="response", response=response, extra_log_data=extra_log_data)

        # After this point, dont_block=False, the queue is empty, and we
        # have a pre-existing queue, so we wait for new events.
        if was_connected:
            logging.info(
                "Disconnected handler for queue %s (%s/%s)",
                queue_id,
                user_profile_id,
                client_type_name,
            )
    except JsonableError as e:
        return dict(type="error", exception=e)

    client.connect_handler(handler_id, client_type_name)
    return dict(type="async")


def process_presence_event(event: Mapping[str, Any], users: Iterable[int]) -> None:
    assert "user_id" in event
    assert "presence" in event

    print(f"OUTBOUND! about to send out event to some subset of {len(users)} users")

    for user_profile_id in users:
        for client in get_client_descriptors_for_user(user_profile_id):
            if client.accepts_event(event):
                client.add_event(event)


def process_notification(notice: Mapping[str, Any]) -> None:
    event: Mapping[str, Any] = notice["event"]
    users: Union[List[int], List[Mapping[str, Any]]] = notice["users"]
    start_time = time.time()

    assert event["type"] == "presence"
    process_presence_event(event, cast(List[int], users))

    logging.info(
        "Tornado: Event %s for %s users took %sms",
        event["type"],
        len(users),
        int(1000 * (time.time() - start_time)),
    )


def get_wrapped_process_notification(queue_name: str) -> Callable[[List[Dict[str, Any]]], None]:
    def failure_processor(notice: Dict[str, Any]) -> None:
        logging.error(
            "Maximum retries exceeded for Tornado notice:%s\nStack trace:\n%s\n",
            notice,
            traceback.format_exc(),
        )

    def wrapped_process_notification(notices: List[Dict[str, Any]]) -> None:
        print("PRESENCE notices", notices)
        for notice in notices:
            try:
                process_notification(notice)
            except Exception:
                retry_event(queue_name, notice, failure_processor)

    return wrapped_process_notification

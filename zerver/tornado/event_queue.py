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
from functools import cache
from typing import (
    AbstractSet,
    Any,
    Callable,
    Collection,
    Deque,
    Dict,
    Iterable,
    List,
    Literal,
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
from typing_extensions import override

from version import API_FEATURE_LEVEL, ZULIP_MERGE_BASE, ZULIP_VERSION
from zerver.lib.exceptions import JsonableError
from zerver.lib.message_cache import MessageDict
from zerver.lib.narrow_helpers import narrow_dataclasses_from_tuples
from zerver.lib.narrow_predicate import build_narrow_predicate
from zerver.lib.notification_data import UserMessageNotificationsData
from zerver.lib.queue import queue_json_publish, retry_event
from zerver.middleware import async_request_timer_restart
from zerver.models import CustomProfileField
from zerver.tornado.descriptors import clear_descriptor_by_handler_id, set_descriptor_by_handler_id
from zerver.tornado.exceptions import BadEventQueueIdError
from zerver.tornado.handlers import finish_handler, get_handler_by_id, handler_stats_string

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
        event_types: Optional[Sequence[str]],
        client_type_name: str,
        apply_markdown: bool = True,
        client_gravatar: bool = True,
        slim_presence: bool = False,
        all_public_streams: bool = False,
        lifespan_secs: int = 0,
        narrow: Collection[Sequence[str]] = [],
        bulk_message_deletion: bool = False,
        stream_typing_notifications: bool = False,
        user_settings_object: bool = False,
        pronouns_field_type_supported: bool = True,
        linkifier_url_template: bool = False,
        user_list_incomplete: bool = False,
    ) -> None:
        # TODO: We eventually want to upstream this code to the caller, but
        # serialization concerns make it a bit difficult.
        modern_narrow = narrow_dataclasses_from_tuples(narrow)

        # These objects are serialized on shutdown and restored on restart.
        # If fields are added or semantics are changed, temporary code must be
        # added to load_event_queues() to update the restored objects.
        # Additionally, the to_dict and from_dict methods must be updated
        self.user_profile_id = user_profile_id
        self.realm_id = realm_id
        self.current_handler_id: Optional[int] = None
        self.current_client_name: Optional[str] = None
        self.event_queue = event_queue
        self.event_types = event_types
        self.last_connection_time = time.time()
        self.apply_markdown = apply_markdown
        self.client_gravatar = client_gravatar
        self.slim_presence = slim_presence
        self.all_public_streams = all_public_streams
        self.client_type_name = client_type_name
        self._timeout_handle: Any = None  # TODO: should be return type of ioloop.call_later
        self.narrow = narrow
        self.narrow_predicate = build_narrow_predicate(modern_narrow)
        self.bulk_message_deletion = bulk_message_deletion
        self.stream_typing_notifications = stream_typing_notifications
        self.user_settings_object = user_settings_object
        self.pronouns_field_type_supported = pronouns_field_type_supported
        self.linkifier_url_template = linkifier_url_template
        self.user_list_incomplete = user_list_incomplete

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
            event_types=self.event_types,
            last_connection_time=self.last_connection_time,
            apply_markdown=self.apply_markdown,
            client_gravatar=self.client_gravatar,
            slim_presence=self.slim_presence,
            all_public_streams=self.all_public_streams,
            narrow=self.narrow,
            client_type_name=self.client_type_name,
            bulk_message_deletion=self.bulk_message_deletion,
            stream_typing_notifications=self.stream_typing_notifications,
            user_settings_object=self.user_settings_object,
            pronouns_field_type_supported=self.pronouns_field_type_supported,
            linkifier_url_template=self.linkifier_url_template,
            user_list_incomplete=self.user_list_incomplete,
        )

    @override
    def __repr__(self) -> str:
        return f"ClientDescriptor<{self.event_queue.id}>"

    @classmethod
    def from_dict(cls, d: MutableMapping[str, Any]) -> "ClientDescriptor":
        if "client_type" in d:
            # Temporary migration for the rename of client_type to client_type_name
            d["client_type_name"] = d["client_type"]
        if "client_gravatar" not in d:
            # Temporary migration for the addition of the client_gravatar field
            d["client_gravatar"] = False

        if "slim_presence" not in d:
            d["slim_presence"] = False

        ret = cls(
            d["user_profile_id"],
            d["realm_id"],
            EventQueue.from_dict(d["event_queue"]),
            d["event_types"],
            d["client_type_name"],
            d["apply_markdown"],
            d["client_gravatar"],
            d["slim_presence"],
            d["all_public_streams"],
            d["queue_timeout"],
            d.get("narrow", []),
            d.get("bulk_message_deletion", False),
            d.get("stream_typing_notifications", False),
            d.get("user_settings_object", False),
            d.get("pronouns_field_type_supported", True),
            d.get("linkifier_url_template", False),
            d.get("user_list_incomplete", False),
        )
        ret.last_connection_time = d["last_connection_time"]
        return ret

    def add_event(self, event: Mapping[str, Any]) -> None:
        if self.current_handler_id is not None:
            handler = get_handler_by_id(self.current_handler_id)
            if handler is not None:
                assert handler._request is not None
                async_request_timer_restart(handler._request)

        self.event_queue.push(event)
        self.finish_current_handler()

    def finish_current_handler(self) -> bool:
        if self.current_handler_id is None:
            return False
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

    def accepts_event(self, event: Mapping[str, Any]) -> bool:
        if self.event_types is not None:
            if event["type"] not in self.event_types:
                return False
            if event["type"] == "muted_topics" and "user_topic" in self.event_types:
                # Suppress muted_topics events for clients that
                # support user_topic. This allows clients to request
                # both the user_topic and muted_topics event types,
                # and receive the duplicate muted_topics data only on
                # older servers that don't support user_topic.
                return False
        if event["type"] == "message":
            return self.narrow_predicate(message=event["message"], flags=event["flags"])
        if event["type"] == "typing" and "stream_id" in event:
            # Typing notifications for stream messages are only
            # delivered if the stream_typing_notifications
            # client_capability is enabled, for backwards compatibility.
            return self.stream_typing_notifications
        if self.user_settings_object and event["type"] in [
            "update_display_settings",
            "update_global_notifications",
        ]:
            # 'update_display_settings' and 'update_global_notifications'
            # events are sent only if user_settings_object is False,
            # otherwise only 'user_settings' event is sent.
            return False
        return True

    # TODO: Refactor so we don't need this function
    def accepts_messages(self) -> bool:
        return self.event_types is None or "message" in self.event_types

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


def compute_full_event_type(event: Mapping[str, Any]) -> str:
    if event["type"] == "update_message_flags":
        if event["all"]:
            # Put the "all" case in its own category
            return "all_flags/{}/{}".format(event["flag"], event["operation"])
        return "flags/{}/{}".format(event["operation"], event["flag"])
    return event["type"]


class EventQueue:
    def __init__(self, id: str) -> None:
        # When extending this list of properties, one must be sure to
        # update to_dict and from_dict.

        self.queue: Deque[Dict[str, Any]] = deque()
        self.next_event_id: int = 0
        # will only be None for migration from old versions
        self.newest_pruned_id: Optional[int] = -1
        self.id: str = id
        self.virtual_events: Dict[str, Dict[str, Any]] = {}

    def to_dict(self) -> Dict[str, Any]:
        # If you add a new key to this dict, make sure you add appropriate
        # migration code in from_dict or load_event_queues to account for
        # loading event queues that lack that key.
        d = dict(
            id=self.id,
            next_event_id=self.next_event_id,
            queue=list(self.queue),
            virtual_events=self.virtual_events,
        )
        if self.newest_pruned_id is not None:
            d["newest_pruned_id"] = self.newest_pruned_id
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EventQueue":
        ret = cls(d["id"])
        ret.next_event_id = d["next_event_id"]
        ret.newest_pruned_id = d.get("newest_pruned_id")
        ret.queue = deque(d["queue"])
        ret.virtual_events = d.get("virtual_events", {})
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
        full_event_type = compute_full_event_type(event)
        if full_event_type.startswith("flags/") and not full_event_type.startswith(
            "flags/remove/read"
        ):
            # virtual_events are an optimization that allows certain
            # simple events, such as update_message_flags events that
            # simply contain a list of message IDs to operate on, to
            # be compressed together. This is primarily useful for
            # flags/add/read, where normal Zulip usage will result in
            # many small flags/add/read events as users scroll.
            #
            # We need to exclude flags/remove/read, because it has an
            # extra message_details field that cannot be compressed.
            #
            # BUG: This compression algorithm is incorrect in the
            # presence of mark-as-unread, since it does not respect
            # the ordering of "mark as read" and "mark as unread"
            # updates for a given message.
            if full_event_type not in self.virtual_events:
                self.virtual_events[full_event_type] = copy.deepcopy(event)
                return

            # Update the virtual event with the values from the event
            virtual_event = self.virtual_events[full_event_type]
            virtual_event["id"] = event["id"]
            virtual_event["messages"] += event["messages"]
            if "timestamp" in event:
                virtual_event["timestamp"] = event["timestamp"]

        else:
            self.queue.append(event)

    # Note that pop ignores virtual events.  This is fine in our
    # current usage since virtual events should always be resolved to
    # a real event before being given to users.
    def pop(self) -> Dict[str, Any]:
        return self.queue.popleft()

    def empty(self) -> bool:
        return len(self.queue) == 0 and len(self.virtual_events) == 0

    # See the comment on pop; that applies here as well
    def prune(self, through_id: int) -> None:
        while len(self.queue) != 0 and self.queue[0]["id"] <= through_id:
            self.newest_pruned_id = self.queue[0]["id"]
            self.pop()

    def contents(self, include_internal_data: bool = False) -> List[Dict[str, Any]]:
        contents: List[Dict[str, Any]] = []
        virtual_id_map: Dict[str, Dict[str, Any]] = {}
        for event_type in self.virtual_events:
            virtual_id_map[self.virtual_events[event_type]["id"]] = self.virtual_events[event_type]
        virtual_ids = sorted(virtual_id_map.keys())

        # Merge the virtual events into their final place in the queue
        index = 0
        length = len(virtual_ids)
        for event in self.queue:
            while index < length and virtual_ids[index] < event["id"]:
                contents.append(virtual_id_map[virtual_ids[index]])
                index += 1
            contents.append(event)
        while index < length:
            contents.append(virtual_id_map[virtual_ids[index]])
            index += 1

        self.virtual_events = {}
        self.queue = deque(contents)

        if include_internal_data:
            return contents
        return prune_internal_data(contents)


def prune_internal_data(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prunes the internal_data data structures, which are not intended to
    be exposed to API clients.
    """
    events = copy.deepcopy(events)
    for event in events:
        if event["type"] == "message" and "internal_data" in event:
            del event["internal_data"]
    return events


# Queue-ids which still need to be sent a web_reload_client event.
# This is treated as an ordered set, which is sorted by realm-id when
# loaded from disk.
web_reload_clients: Dict[str, Literal[True]] = {}

# maps queue ids to client descriptors
clients: Dict[str, ClientDescriptor] = {}
# maps user id to list of client descriptors
user_clients: Dict[int, List[ClientDescriptor]] = {}
# maps realm id to list of client descriptors with all_public_streams=True
realm_clients_all_streams: Dict[int, List[ClientDescriptor]] = {}

# list of registered gc hooks.
# each one will be called with a user profile id, queue, and bool
# last_for_client that is true if this is the last queue pertaining
# to this user_profile_id
# that is about to be deleted
gc_hooks: List[Callable[[int, ClientDescriptor, bool], None]] = []


def clear_client_event_queues_for_testing() -> None:
    assert settings.TEST_SUITE
    clients.clear()
    web_reload_clients.clear()
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


def get_client_descriptors_for_realm_all_streams(realm_id: int) -> List[ClientDescriptor]:
    return realm_clients_all_streams.get(realm_id, [])


def add_to_client_dicts(client: ClientDescriptor) -> None:
    user_clients.setdefault(client.user_profile_id, []).append(client)
    if client.all_public_streams or client.narrow != []:
        realm_clients_all_streams.setdefault(client.realm_id, []).append(client)


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
        if id in web_reload_clients:
            del web_reload_clients[id]
        for cb in gc_hooks:
            cb(
                clients[id].user_profile_id,
                clients[id],
                clients[id].user_profile_id not in user_clients,
            )
        del clients[id]


def gc_event_queues(port: int) -> None:
    # We cannot use perf_counter here, since we store and compare UNIX
    # timestamps to it in the queues.
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
    if settings.TORNADO_PROCESSES == 1:
        # Use non-port-aware, legacy version.
        if last:
            return settings.JSON_PERSISTENT_QUEUE_FILENAME_PATTERN % ("",) + ".last"
        return settings.JSON_PERSISTENT_QUEUE_FILENAME_PATTERN % ("",)
    if last:
        return settings.JSON_PERSISTENT_QUEUE_FILENAME_PATTERN % ("." + str(port) + ".last",)
    return settings.JSON_PERSISTENT_QUEUE_FILENAME_PATTERN % ("." + str(port),)


def dump_event_queues(port: int) -> None:
    start = time.perf_counter()

    with open(persistent_queue_filename(port), "wb") as stored_queues:
        stored_queues.write(
            orjson.dumps([(qid, client.to_dict()) for (qid, client) in clients.items()])
        )

    if len(clients) > 0 or settings.PRODUCTION:
        logging.info(
            "Tornado %d dumped %d event queues in %.3fs",
            port,
            len(clients),
            time.perf_counter() - start,
        )


def load_event_queues(port: int) -> None:
    global clients
    start = time.perf_counter()

    try:
        with open(persistent_queue_filename(port), "rb") as stored_queues:
            data = orjson.loads(stored_queues.read())
    except FileNotFoundError:
        pass
    except orjson.JSONDecodeError:
        logging.exception("Tornado %d could not deserialize event queues", port, stack_info=True)
    else:
        try:
            clients = {qid: ClientDescriptor.from_dict(client) for (qid, client) in data}
        except Exception:
            logging.exception(
                "Tornado %d could not deserialize event queues", port, stack_info=True
            )

    mark_clients_to_reload(clients.keys())

    for client in clients.values():
        # Put code for migrations due to event queue data format changes here

        add_to_client_dicts(client)

    if len(clients) > 0 or settings.PRODUCTION:
        logging.info(
            "Tornado %d loaded %d event queues in %.3fs",
            port,
            len(clients),
            time.perf_counter() - start,
        )


def send_restart_events() -> None:
    event: Dict[str, Any] = dict(
        type="restart",
        zulip_version=ZULIP_VERSION,
        zulip_merge_base=ZULIP_MERGE_BASE,
        zulip_feature_level=API_FEATURE_LEVEL,
        server_generation=settings.SERVER_GENERATION,
    )
    for client in clients.values():
        if client.accepts_event(event):
            client.add_event(event)


def mark_clients_to_reload(queue_ids: Iterable[str]) -> None:
    # Build web_reload_clients, which is a sorted-by-realm-id list of
    # website client queue-ids which were were loaded from old Tornado
    # instances.  We use an (ordered) dict to make removing one be
    # O(1), as well as pulling an ordered N of them to be O(N).  We
    # sort by realm_id so that restarts are rolling by realm.
    for qid in sorted(
        (qid for qid in queue_ids if clients[qid].accepts_event({"type": "web_reload_client"})),
        key=lambda qid: clients[qid].realm_id,
    ):
        web_reload_clients[qid] = True


def send_web_reload_client_events(immediate: bool = False, count: Optional[int] = None) -> int:
    event: Dict[str, Any] = dict(
        type="web_reload_client",
        immediate=immediate,
    )
    if count is None:
        count = len(web_reload_clients)
    queue_ids = list(web_reload_clients.keys())[:count]
    for qid in queue_ids:
        del web_reload_clients[qid]
        client = clients[qid]
        if client.accepts_event(event):
            client.add_event(event)
    return len(queue_ids)


async def setup_event_queue(
    server: tornado.httpserver.HTTPServer, port: int, send_reloads: bool = True
) -> None:
    if not settings.TEST_SUITE:
        load_event_queues(port)
        autoreload.add_reload_hook(lambda: dump_event_queues(port))

    with suppress(OSError):
        os.rename(persistent_queue_filename(port), persistent_queue_filename(port, last=True))

    # Set up event queue garbage collection
    pc = tornado.ioloop.PeriodicCallback(lambda: gc_event_queues(port), EVENT_QUEUE_GC_FREQ_MSECS)
    pc.start()

    send_restart_events()
    if send_reloads:
        send_web_reload_client_events(immediate=settings.DEVELOPMENT)


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


def build_offline_notification(user_profile_id: int, message_id: int) -> Dict[str, Any]:
    return {
        "user_profile_id": user_profile_id,
        "message_id": message_id,
    }


def missedmessage_hook(
    user_profile_id: int, client: ClientDescriptor, last_for_client: bool
) -> None:
    """The receiver_is_off_zulip logic used to determine whether a user
    has no active client suffers from a somewhat fundamental race
    condition.  If the client is no longer on the Internet,
    receiver_is_off_zulip will still return False for
    DEFAULT_EVENT_QUEUE_TIMEOUT_SECS, until the queue is
    garbage-collected.  This would cause us to reliably miss
    push/email notifying users for messages arriving during the
    DEFAULT_EVENT_QUEUE_TIMEOUT_SECS after they suspend their laptop (for
    example).  We address this by, when the queue is garbage-collected
    at the end of those 10 minutes, checking to see if it's the last
    one, and if so, potentially triggering notifications to the user
    at that time, resulting in at most a DEFAULT_EVENT_QUEUE_TIMEOUT_SECS
    delay in the arrival of their notifications.

    As Zulip's APIs get more popular and the mobile apps start using
    long-lived event queues for perf optimization, future versions of
    this will likely need to replace checking `last_for_client` with
    something more complicated, so that we only consider clients like
    web browsers, not the mobile apps or random API scripts.
    """
    # Only process missedmessage hook when the last queue for a
    # client has been garbage collected
    if not last_for_client:
        return

    for event in client.event_queue.contents(include_internal_data=True):
        if event["type"] != "message":
            continue
        internal_data = event.get("internal_data", {})
        sender_id = event["message"]["sender_id"]

        # TODO/compatibility: Translation code for the rename of
        # `pm_push_notify` to `dm_push_notify`. Remove this when
        # one can no longer directly upgrade from 7.x to main.
        dm_push_notify = False
        if "dm_push_notify" in internal_data:
            dm_push_notify = internal_data.get("dm_push_notify")
        elif "pm_push_notify" in internal_data:
            dm_push_notify = internal_data.get("pm_push_notify")

        # TODO/compatibility: Translation code for the rename of
        # `pm_email_notify` to `dm_email_notify`. Remove this when
        # one can no longer directly upgrade from 7.x to main.
        dm_email_notify = False
        if "dm_email_notify" in internal_data:
            dm_email_notify = internal_data.get("dm_email_notify")
        elif "pm_email_notify" in internal_data:
            dm_email_notify = internal_data.get("pm_email_notify")

        # TODO/compatibility: Translation code for the rename of
        # `wildcard_mention_push_notify` to `stream_wildcard_mention_push_notify`.
        # Remove this when one can no longer directly upgrade from 7.x to main.
        stream_wildcard_mention_push_notify = False
        if "stream_wildcard_mention_push_notify" in internal_data:
            stream_wildcard_mention_push_notify = internal_data.get(
                "stream_wildcard_mention_push_notify"
            )
        elif "wildcard_mention_push_notify" in internal_data:
            stream_wildcard_mention_push_notify = internal_data.get("wildcard_mention_push_notify")

        # TODO/compatibility: Translation code for the rename of
        # `wildcard_mention_email_notify` to `stream_wildcard_mention_email_notify`.
        # Remove this when one can no longer directly upgrade from 7.x to main.
        stream_wildcard_mention_email_notify = False
        if "stream_wildcard_mention_email_notify" in internal_data:
            stream_wildcard_mention_email_notify = internal_data.get(
                "stream_wildcard_mention_email_notify"
            )
        elif "wildcard_mention_email_notify" in internal_data:
            stream_wildcard_mention_email_notify = internal_data.get(
                "wildcard_mention_email_notify"
            )

        user_notifications_data = UserMessageNotificationsData(
            user_id=user_profile_id,
            sender_is_muted=internal_data.get("sender_is_muted", False),
            dm_push_notify=dm_push_notify,
            dm_email_notify=dm_email_notify,
            mention_push_notify=internal_data.get("mention_push_notify", False),
            mention_email_notify=internal_data.get("mention_email_notify", False),
            topic_wildcard_mention_push_notify=internal_data.get(
                "topic_wildcard_mention_push_notify", False
            ),
            topic_wildcard_mention_email_notify=internal_data.get(
                "topic_wildcard_mention_email_notify", False
            ),
            stream_wildcard_mention_push_notify=stream_wildcard_mention_push_notify,
            stream_wildcard_mention_email_notify=stream_wildcard_mention_email_notify,
            stream_push_notify=internal_data.get("stream_push_notify", False),
            stream_email_notify=internal_data.get("stream_email_notify", False),
            followed_topic_push_notify=internal_data.get("followed_topic_push_notify", False),
            followed_topic_email_notify=internal_data.get("followed_topic_email_notify", False),
            topic_wildcard_mention_in_followed_topic_push_notify=internal_data.get(
                "topic_wildcard_mention_in_followed_topic_push_notify", False
            ),
            topic_wildcard_mention_in_followed_topic_email_notify=internal_data.get(
                "topic_wildcard_mention_in_followed_topic_email_notify", False
            ),
            stream_wildcard_mention_in_followed_topic_push_notify=internal_data.get(
                "stream_wildcard_mention_in_followed_topic_push_notify", False
            ),
            stream_wildcard_mention_in_followed_topic_email_notify=internal_data.get(
                "stream_wildcard_mention_in_followed_topic_email_notify", False
            ),
            # Since one is by definition idle, we don't need to check online_push_enabled
            online_push_enabled=False,
            disable_external_notifications=internal_data.get(
                "disable_external_notifications", False
            ),
        )

        mentioned_user_group_id = internal_data.get("mentioned_user_group_id")

        # Since we just GC'd the last event queue, the user is definitely idle.
        idle = True

        message_id = event["message"]["id"]
        # Pass on the information on whether a push or email notification was already sent.
        already_notified = dict(
            push_notified=internal_data.get("push_notified", False),
            email_notified=internal_data.get("email_notified", False),
        )
        maybe_enqueue_notifications(
            user_notifications_data=user_notifications_data,
            acting_user_id=sender_id,
            message_id=message_id,
            mentioned_user_group_id=mentioned_user_group_id,
            idle=idle,
            already_notified=already_notified,
        )


def receiver_is_off_zulip(user_profile_id: int) -> bool:
    # If a user has no message-receiving event queues, they've got no open zulip
    # session so we notify them.
    all_client_descriptors = get_client_descriptors_for_user(user_profile_id)
    message_event_queues = [
        client for client in all_client_descriptors if client.accepts_messages()
    ]
    off_zulip = len(message_event_queues) == 0
    return off_zulip


def maybe_enqueue_notifications(
    *,
    user_notifications_data: UserMessageNotificationsData,
    acting_user_id: int,
    message_id: int,
    mentioned_user_group_id: Optional[int],
    idle: bool,
    already_notified: Dict[str, bool],
) -> Dict[str, bool]:
    """This function has a complete unit test suite in
    `test_enqueue_notifications` that should be expanded as we add
    more features here.

    See https://zulip.readthedocs.io/en/latest/subsystems/notifications.html
    for high-level design documentation.
    """
    notified: Dict[str, bool] = {}

    if user_notifications_data.is_push_notifiable(acting_user_id, idle):
        notice = build_offline_notification(user_notifications_data.user_id, message_id)
        notice["trigger"] = user_notifications_data.get_push_notification_trigger(
            acting_user_id, idle
        )
        notice["type"] = "add"
        notice["mentioned_user_group_id"] = mentioned_user_group_id
        if not already_notified.get("push_notified"):
            if settings.MOBILE_NOTIFICATIONS_SHARDS > 1:
                shard_id = (
                    user_notifications_data.user_id % settings.MOBILE_NOTIFICATIONS_SHARDS + 1
                )
                queue_json_publish(f"missedmessage_mobile_notifications_shard{shard_id}", notice)
            else:
                queue_json_publish("missedmessage_mobile_notifications", notice)
            notified["push_notified"] = True

    # Send missed_message emails if a direct message or a
    # mention.  Eventually, we'll add settings to allow email
    # notifications to match the model of push notifications
    # above.
    if user_notifications_data.is_email_notifiable(acting_user_id, idle):
        notice = build_offline_notification(user_notifications_data.user_id, message_id)
        notice["trigger"] = user_notifications_data.get_email_notification_trigger(
            acting_user_id, idle
        )
        notice["mentioned_user_group_id"] = mentioned_user_group_id
        if not already_notified.get("email_notified"):
            queue_json_publish("missedmessage_emails", notice, lambda notice: None)
            notified["email_notified"] = True

    return notified


class ClientInfo(TypedDict):
    client: ClientDescriptor
    flags: Collection[str]
    is_sender: bool


def get_client_info_for_message_event(
    event_template: Mapping[str, Any], users: Iterable[Mapping[str, Any]]
) -> Dict[str, ClientInfo]:
    """
    Return client info for all the clients interested in a message.
    This basically includes clients for users who are recipients
    of the message, with some nuances for bots that auto-subscribe
    to all streams, plus users who may be mentioned, etc.
    """

    send_to_clients: Dict[str, ClientInfo] = {}

    sender_queue_id: Optional[str] = event_template.get("sender_queue_id", None)

    def is_sender_client(client: ClientDescriptor) -> bool:
        return (sender_queue_id is not None) and client.event_queue.id == sender_queue_id

    # If we're on a public stream, look for clients (typically belonging to
    # bots) that are registered to get events for ALL streams.
    if "stream_name" in event_template and not event_template.get("invite_only"):
        realm_id = event_template["realm_id"]
        for client in get_client_descriptors_for_realm_all_streams(realm_id):
            send_to_clients[client.event_queue.id] = dict(
                client=client,
                flags=[],
                is_sender=is_sender_client(client),
            )

    for user_data in users:
        user_profile_id: int = user_data["id"]
        flags: Collection[str] = user_data.get("flags", [])

        for client in get_client_descriptors_for_user(user_profile_id):
            send_to_clients[client.event_queue.id] = dict(
                client=client,
                flags=flags,
                is_sender=is_sender_client(client),
            )

    return send_to_clients


def process_message_event(
    event_template: Mapping[str, Any], users: Collection[Mapping[str, Any]]
) -> None:
    """See
    https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html
    for high-level documentation on this subsystem.
    """
    send_to_clients = get_client_info_for_message_event(event_template, users)

    presence_idle_user_ids = set(event_template.get("presence_idle_user_ids", []))
    online_push_user_ids = set(event_template.get("online_push_user_ids", []))

    # TODO/compatibility: Translation code for the rename of
    # `pm_mention_push_disabled_user_ids` to `dm_mention_push_disabled_user_ids`.
    # Remove this when one can no longer directly upgrade from 7.x to main.
    dm_mention_push_disabled_user_ids = set()
    if "dm_mention_push_disabled_user_ids" in event_template:
        dm_mention_push_disabled_user_ids = set(
            event_template.get("dm_mention_push_disabled_user_ids", [])
        )
    elif "pm_mention_push_disabled_user_ids" in event_template:
        dm_mention_push_disabled_user_ids = set(
            event_template.get("pm_mention_push_disabled_user_ids", [])
        )

    # TODO/compatibility: Translation code for the rename of
    # `pm_mention_email_disabled_user_ids` to `dm_mention_email_disabled_user_ids`.
    # Remove this when one can no longer directly upgrade from 7.x to main.
    dm_mention_email_disabled_user_ids = set()
    if "dm_mention_email_disabled_user_ids" in event_template:
        dm_mention_email_disabled_user_ids = set(
            event_template.get("dm_mention_email_disabled_user_ids", [])
        )
    elif "pm_mention_email_disabled_user_ids" in event_template:
        dm_mention_email_disabled_user_ids = set(
            event_template.get("pm_mention_email_disabled_user_ids", [])
        )

    stream_push_user_ids = set(event_template.get("stream_push_user_ids", []))
    stream_email_user_ids = set(event_template.get("stream_email_user_ids", []))
    topic_wildcard_mention_user_ids = set(event_template.get("topic_wildcard_mention_user_ids", []))

    # TODO/compatibility: Translation code for the rename of
    # `wildcard_mention_user_ids` to `stream_wildcard_mention_user_ids`.
    # Remove this when one can no longer directly upgrade from 7.x to main.
    stream_wildcard_mention_user_ids = set()
    if "stream_wildcard_mention_user_ids" in event_template:
        stream_wildcard_mention_user_ids = set(
            event_template.get("stream_wildcard_mention_user_ids", [])
        )
    elif "wildcard_mention_user_ids" in event_template:
        stream_wildcard_mention_user_ids = set(event_template.get("wildcard_mention_user_ids", []))

    followed_topic_push_user_ids = set(event_template.get("followed_topic_push_user_ids", []))
    followed_topic_email_user_ids = set(event_template.get("followed_topic_email_user_ids", []))
    topic_wildcard_mention_in_followed_topic_user_ids = set(
        event_template.get("topic_wildcard_mention_in_followed_topic_user_ids", [])
    )
    stream_wildcard_mention_in_followed_topic_user_ids = set(
        event_template.get("stream_wildcard_mention_in_followed_topic_user_ids", [])
    )
    muted_sender_user_ids = set(event_template.get("muted_sender_user_ids", []))
    all_bot_user_ids = set(event_template.get("all_bot_user_ids", []))
    disable_external_notifications = event_template.get("disable_external_notifications", False)
    user_ids_without_access_to_sender = event_template.get("user_ids_without_access_to_sender", [])
    realm_host = event_template.get("realm_host", "")

    wide_dict: Dict[str, Any] = event_template["message_dict"]

    # Temporary transitional code: Zulip servers that have message
    # events in their event queues and upgrade to the new version
    # that expects sender_delivery_email in these events will
    # throw errors processing events.  We can remove this block
    # once we don't expect anyone to be directly upgrading from
    # 2.0.x to the latest Zulip.
    if "sender_delivery_email" not in wide_dict:  # nocoverage
        wide_dict["sender_delivery_email"] = wide_dict["sender_email"]

    sender_id: int = wide_dict["sender_id"]
    message_id: int = wide_dict["id"]
    recipient_type_name: str = wide_dict["type"]
    sending_client: str = wide_dict["client"]

    @cache
    def get_client_payload(
        apply_markdown: bool, client_gravatar: bool, can_access_sender: bool
    ) -> Dict[str, Any]:
        return MessageDict.finalize_payload(
            wide_dict,
            apply_markdown=apply_markdown,
            client_gravatar=client_gravatar,
            can_access_sender=can_access_sender,
            realm_host=realm_host,
        )

    # Extra user-specific data to include
    extra_user_data: Dict[int, Any] = {}

    for user_data in users:
        user_profile_id: int = user_data["id"]
        flags: Collection[str] = user_data.get("flags", [])
        mentioned_user_group_id: Optional[int] = user_data.get("mentioned_user_group_id")

        # If the recipient was offline and the message was a (1:1 or group) direct message
        # to them or they were @-notified potentially notify more immediately
        private_message = recipient_type_name == "private"
        user_notifications_data = UserMessageNotificationsData.from_user_id_sets(
            user_id=user_profile_id,
            flags=flags,
            private_message=private_message,
            disable_external_notifications=disable_external_notifications,
            online_push_user_ids=online_push_user_ids,
            dm_mention_push_disabled_user_ids=dm_mention_push_disabled_user_ids,
            dm_mention_email_disabled_user_ids=dm_mention_email_disabled_user_ids,
            stream_push_user_ids=stream_push_user_ids,
            stream_email_user_ids=stream_email_user_ids,
            topic_wildcard_mention_user_ids=topic_wildcard_mention_user_ids,
            stream_wildcard_mention_user_ids=stream_wildcard_mention_user_ids,
            followed_topic_push_user_ids=followed_topic_push_user_ids,
            followed_topic_email_user_ids=followed_topic_email_user_ids,
            topic_wildcard_mention_in_followed_topic_user_ids=topic_wildcard_mention_in_followed_topic_user_ids,
            stream_wildcard_mention_in_followed_topic_user_ids=stream_wildcard_mention_in_followed_topic_user_ids,
            muted_sender_user_ids=muted_sender_user_ids,
            all_bot_user_ids=all_bot_user_ids,
        )

        # Calling asdict would be slow, as it does a deep copy; pull
        # the attributes out directly and perform a shallow copy, as
        # we do intend to adjust the dict.
        internal_data = {**vars(user_notifications_data)}

        # Remove fields sent through other pipes to save some space.
        internal_data.pop("user_id")
        internal_data["mentioned_user_group_id"] = mentioned_user_group_id
        extra_user_data[user_profile_id] = dict(internal_data=internal_data)

        # If the message isn't notifiable had the user been idle, then the user
        # shouldn't receive notifications even if they were online. In that case we can
        # avoid the more expensive `receiver_is_off_zulip` call, and move on to process
        # the next user.
        if not user_notifications_data.is_notifiable(acting_user_id=sender_id, idle=True):
            continue

        idle = receiver_is_off_zulip(user_profile_id) or (user_profile_id in presence_idle_user_ids)

        extra_user_data[user_profile_id]["internal_data"].update(
            maybe_enqueue_notifications(
                user_notifications_data=user_notifications_data,
                acting_user_id=sender_id,
                message_id=message_id,
                mentioned_user_group_id=mentioned_user_group_id,
                idle=idle,
                already_notified={},
            )
        )

    for client_data in send_to_clients.values():
        client = client_data["client"]
        flags = client_data["flags"]
        is_sender: bool = client_data.get("is_sender", False)
        extra_data: Optional[Mapping[str, bool]] = extra_user_data.get(client.user_profile_id, None)

        if not client.accepts_messages():
            # The actual check is the accepts_event() check below;
            # this line is just an optimization to avoid copying
            # message data unnecessarily
            continue

        can_access_sender = client.user_profile_id not in user_ids_without_access_to_sender
        message_dict = get_client_payload(
            client.apply_markdown, client.client_gravatar, can_access_sender
        )

        # Make sure Zephyr mirroring bots know whether stream is invite-only
        if "mirror" in client.client_type_name and event_template.get("invite_only"):
            message_dict = message_dict.copy()
            message_dict["invite_only_stream"] = True

        user_event: Dict[str, Any] = dict(type="message", message=message_dict, flags=flags)
        if extra_data is not None:
            user_event.update(extra_data)

        if is_sender:
            local_message_id = event_template.get("local_id", None)
            if local_message_id is not None:
                user_event["local_message_id"] = local_message_id

        if not client.accepts_event(user_event):
            continue

        # The below prevents (Zephyr) mirroring loops.
        if "mirror" in sending_client and sending_client.lower() == client.client_type_name.lower():
            continue

        client.add_event(user_event)


def process_presence_event(event: Mapping[str, Any], users: Iterable[int]) -> None:
    if "user_id" not in event:
        # We only recently added `user_id` to presence data.
        # Any old events in our queue can just be dropped,
        # since presence events are pretty ephemeral in nature.
        logging.warning("Dropping some obsolete presence events after upgrade.")

    slim_event = dict(
        type="presence",
        user_id=event["user_id"],
        server_timestamp=event["server_timestamp"],
        presence=event["presence"],
    )

    legacy_event = dict(
        type="presence",
        user_id=event["user_id"],
        email=event["email"],
        server_timestamp=event["server_timestamp"],
        presence=event["presence"],
    )

    for user_profile_id in users:
        for client in get_client_descriptors_for_user(user_profile_id):
            if client.accepts_event(event):
                if client.slim_presence:
                    client.add_event(slim_event)
                else:
                    client.add_event(legacy_event)


def process_event(event: Mapping[str, Any], users: Iterable[int]) -> None:
    for user_profile_id in users:
        for client in get_client_descriptors_for_user(user_profile_id):
            if client.accepts_event(event):
                client.add_event(event)


def process_deletion_event(event: Mapping[str, Any], users: Iterable[int]) -> None:
    for user_profile_id in users:
        for client in get_client_descriptors_for_user(user_profile_id):
            if not client.accepts_event(event):
                continue

            # For clients which support message deletion in bulk, we
            # send a list of msgs_ids together, otherwise we send a
            # delete event for each message.  All clients will be
            # required to support bulk_message_deletion in the future;
            # this logic is intended for backwards-compatibility only.
            if client.bulk_message_deletion:
                client.add_event(event)
                continue

            for message_id in event["message_ids"]:
                # We use the following rather than event.copy()
                # because the read-only Mapping type doesn't support .copy().
                compatibility_event = dict(event)
                compatibility_event["message_id"] = message_id
                del compatibility_event["message_ids"]
                client.add_event(compatibility_event)


def process_message_update_event(
    orig_event: Mapping[str, Any], users: Iterable[Mapping[str, Any]]
) -> None:
    # Extract the parameters passed via the event object that don't
    # belong in the actual events.
    event_template = dict(orig_event)
    prior_mention_user_ids = set(event_template.pop("prior_mention_user_ids", []))
    presence_idle_user_ids = set(event_template.pop("presence_idle_user_ids", []))

    # TODO/compatibility: Translation code for the rename of
    # `pm_mention_push_disabled_user_ids` to `dm_mention_push_disabled_user_ids`.
    # Remove this when one can no longer directly upgrade from 7.x to main.
    dm_mention_push_disabled_user_ids = set()
    if "dm_mention_push_disabled_user_ids" in event_template:
        dm_mention_push_disabled_user_ids = set(
            event_template.pop("dm_mention_push_disabled_user_ids")
        )
    elif "pm_mention_push_disabled_user_ids" in event_template:
        dm_mention_push_disabled_user_ids = set(
            event_template.pop("pm_mention_push_disabled_user_ids")
        )

    # TODO/compatibility: Translation code for the rename of
    # `pm_mention_email_disabled_user_ids` to `dm_mention_email_disabled_user_ids`.
    # Remove this when one can no longer directly upgrade from 7.x to main.
    dm_mention_email_disabled_user_ids = set()
    if "dm_mention_email_disabled_user_ids" in event_template:
        dm_mention_email_disabled_user_ids = set(
            event_template.pop("dm_mention_email_disabled_user_ids")
        )
    elif "pm_mention_email_disabled_user_ids" in event_template:
        dm_mention_email_disabled_user_ids = set(
            event_template.pop("pm_mention_email_disabled_user_ids")
        )

    stream_push_user_ids = set(event_template.pop("stream_push_user_ids", []))
    stream_email_user_ids = set(event_template.pop("stream_email_user_ids", []))
    topic_wildcard_mention_user_ids = set(event_template.pop("topic_wildcard_mention_user_ids", []))

    # TODO/compatibility: Translation code for the rename of
    # `wildcard_mention_user_ids` to `stream_wildcard_mention_user_ids`.
    # Remove this when one can no longer directly upgrade from 7.x to main.
    stream_wildcard_mention_user_ids = set()
    if "stream_wildcard_mention_user_ids" in event_template:
        stream_wildcard_mention_user_ids = set(
            event_template.pop("stream_wildcard_mention_user_ids")
        )
    elif "wildcard_mention_user_ids" in event_template:
        stream_wildcard_mention_user_ids = set(event_template.pop("wildcard_mention_user_ids"))

    followed_topic_push_user_ids = set(event_template.pop("followed_topic_push_user_ids", []))
    followed_topic_email_user_ids = set(event_template.pop("followed_topic_email_user_ids", []))
    topic_wildcard_mention_in_followed_topic_user_ids = set(
        event_template.pop("topic_wildcard_mention_in_followed_topic_user_ids", [])
    )
    stream_wildcard_mention_in_followed_topic_user_ids = set(
        event_template.pop("stream_wildcard_mention_in_followed_topic_user_ids", [])
    )
    muted_sender_user_ids = set(event_template.pop("muted_sender_user_ids", []))
    all_bot_user_ids = set(event_template.pop("all_bot_user_ids", []))
    disable_external_notifications = event_template.pop("disable_external_notifications", False)

    # TODO/compatibility: Translation code for the rename of
    # `push_notify_user_ids` to `online_push_user_ids`.  Remove this
    # when one can no longer directly upgrade from 4.x to main.
    online_push_user_ids = set()
    if "online_push_user_ids" in event_template:
        online_push_user_ids = set(event_template.pop("online_push_user_ids"))
    elif "push_notify_user_ids" in event_template:
        online_push_user_ids = set(event_template.pop("push_notify_user_ids"))

    stream_name = event_template.get("stream_name")
    message_id = event_template["message_id"]

    # TODO/compatibility: Modern `update_message` events contain the
    # rendering_only key, which indicates whether the update is a link
    # preview rendering update (not a human action). However, because
    # events may be in the notify_tornado queue at the time we
    # upgrade, we need the below logic to compute rendering_only based
    # on the `user_id` key not being present in legacy events that
    # would have had rendering_only set. Remove this check when one
    # can no longer directly update from 4.x to main.
    if "rendering_only" in event_template:
        rendering_only_update = event_template["rendering_only"]
    else:
        rendering_only_update = "user_id" not in event_template

    for user_data in users:
        user_profile_id = user_data["id"]

        user_event = dict(event_template)  # shallow copy, but deep enough for our needs
        for key in user_data:
            if key != "id":
                user_event[key] = user_data[key]

        # Events where `rendering_only_update` is True come from the
        # do_update_embedded_data code path, and represent rendering
        # previews; there should be no real content changes.
        # Therefore, we know only events where `rendering_only_update`
        # is False possibly send notifications.
        if not rendering_only_update:
            # The user we'll get here will be the sender if the message's
            # content was edited, and the editor for topic edits. That's
            # the correct "acting_user" for both cases.
            acting_user_id = event_template["user_id"]

            flags: Collection[str] = user_event["flags"]
            user_notifications_data = UserMessageNotificationsData.from_user_id_sets(
                user_id=user_profile_id,
                flags=flags,
                private_message=stream_name is None,
                disable_external_notifications=disable_external_notifications,
                online_push_user_ids=online_push_user_ids,
                dm_mention_push_disabled_user_ids=dm_mention_push_disabled_user_ids,
                dm_mention_email_disabled_user_ids=dm_mention_email_disabled_user_ids,
                stream_push_user_ids=stream_push_user_ids,
                stream_email_user_ids=stream_email_user_ids,
                topic_wildcard_mention_user_ids=topic_wildcard_mention_user_ids,
                stream_wildcard_mention_user_ids=stream_wildcard_mention_user_ids,
                followed_topic_push_user_ids=followed_topic_push_user_ids,
                followed_topic_email_user_ids=followed_topic_email_user_ids,
                topic_wildcard_mention_in_followed_topic_user_ids=topic_wildcard_mention_in_followed_topic_user_ids,
                stream_wildcard_mention_in_followed_topic_user_ids=stream_wildcard_mention_in_followed_topic_user_ids,
                muted_sender_user_ids=muted_sender_user_ids,
                all_bot_user_ids=all_bot_user_ids,
            )

            maybe_enqueue_notifications_for_message_update(
                user_notifications_data=user_notifications_data,
                message_id=message_id,
                acting_user_id=acting_user_id,
                private_message=stream_name is None,
                presence_idle=user_profile_id in presence_idle_user_ids,
                prior_mentioned=user_profile_id in prior_mention_user_ids,
            )

        for client in get_client_descriptors_for_user(user_profile_id):
            if client.accepts_event(user_event):
                # We need to do another shallow copy, or we risk
                # sending the same event to multiple clients.
                client.add_event(user_event)


def process_custom_profile_fields_event(event: Mapping[str, Any], users: Iterable[int]) -> None:
    pronouns_type_unsupported_fields = copy.deepcopy(event["fields"])
    for field in pronouns_type_unsupported_fields:
        if field["type"] == CustomProfileField.PRONOUNS:
            field["type"] = CustomProfileField.SHORT_TEXT

    pronouns_type_unsupported_event = dict(
        type="custom_profile_fields", fields=pronouns_type_unsupported_fields
    )

    for user_profile_id in users:
        for client in get_client_descriptors_for_user(user_profile_id):
            if client.accepts_event(event):
                if not client.pronouns_field_type_supported:
                    client.add_event(pronouns_type_unsupported_event)
                    continue
                client.add_event(event)


def process_realm_user_add_event(event: Mapping[str, Any], users: Iterable[int]) -> None:
    user_add_event = dict(event)
    event_for_inaccessible_user = user_add_event.pop("inaccessible_user", False)
    for user_profile_id in users:
        for client in get_client_descriptors_for_user(user_profile_id):
            if client.accepts_event(user_add_event):
                if event_for_inaccessible_user and client.user_list_incomplete:
                    continue
                client.add_event(user_add_event)


def maybe_enqueue_notifications_for_message_update(
    user_notifications_data: UserMessageNotificationsData,
    message_id: int,
    acting_user_id: int,
    private_message: bool,
    presence_idle: bool,
    prior_mentioned: bool,
) -> None:
    if user_notifications_data.sender_is_muted:
        # Never send notifications if the sender has been muted
        return

    if private_message:
        # We don't do offline notifications for direct messages,
        # because we already notified the user of the original
        # message.
        return

    if prior_mentioned:
        # Don't spam people with duplicate mentions.  This is
        # especially important considering that most message
        # edits are simple typo corrections.
        #
        # Note that prior_mention_user_ids contains users who received
        # a wildcard mention as well as normal mentions.
        #
        # TODO: Ideally, that would mean that we exclude here cases
        # where user_profile.wildcard_mentions_notify=False and have
        # those still send a notification.  However, we don't have the
        # data to determine whether or not that was the case at the
        # time the original message was sent, so we can't do that
        # without extending the UserMessage data model.
        return

    if (
        user_notifications_data.stream_push_notify
        or user_notifications_data.stream_email_notify
        or user_notifications_data.followed_topic_push_notify
        or user_notifications_data.followed_topic_email_notify
    ):
        # Currently we assume that if this flag is set to True, then
        # the user already was notified about the earlier message,
        # so we short circuit.  We may handle this more rigorously
        # in the future by looking at something like an AlreadyNotified
        # model.
        return

    idle = presence_idle or receiver_is_off_zulip(user_notifications_data.user_id)

    # We don't yet support custom user group mentions for message edit notifications.
    # Users will still receive notifications (because of the mentioned flag), but those
    # will be as if they were mentioned personally.
    mentioned_user_group_id = None

    maybe_enqueue_notifications(
        user_notifications_data=user_notifications_data,
        message_id=message_id,
        acting_user_id=acting_user_id,
        mentioned_user_group_id=mentioned_user_group_id,
        idle=idle,
        already_notified={},
    )


def reformat_legacy_send_message_event(
    event: Mapping[str, Any], users: Union[List[int], List[Mapping[str, Any]]]
) -> Tuple[MutableMapping[str, Any], Collection[MutableMapping[str, Any]]]:
    # do_send_messages used to send events with users in dict format, with the
    # dict containing the user_id and other data. We later trimmed down the user
    # data to only contain the user_id and the usermessage flags, and put everything
    # else in the event dict as lists.
    # This block handles any old-format events still in the queue during upgrade.

    modern_event = cast(MutableMapping[str, Any], event)
    user_dicts = cast(List[MutableMapping[str, Any]], users)

    # Back-calculate the older all-booleans format data in the `users` dicts into the newer
    # all-lists format, and attach the lists to the `event` object.
    modern_event["online_push_user_ids"] = []
    modern_event["stream_push_user_ids"] = []
    modern_event["stream_email_user_ids"] = []
    modern_event["stream_wildcard_mention_user_ids"] = []
    modern_event["muted_sender_user_ids"] = []

    for user in user_dicts:
        user_id = user["id"]

        if user.pop("stream_push_notify", False):
            modern_event["stream_push_user_ids"].append(user_id)
        if user.pop("stream_email_notify", False):
            modern_event["stream_email_user_ids"].append(user_id)
        if user.pop("wildcard_mention_notify", False):
            modern_event["stream_wildcard_mention_user_ids"].append(user_id)
        if user.pop("sender_is_muted", False):
            modern_event["muted_sender_user_ids"].append(user_id)

        # TODO/compatibility: Another translation code block for the rename of
        # `always_push_notify` to `online_push_enabled`.  Remove this
        # when one can no longer directly upgrade from 4.x to 5.0-dev.
        if user.pop("online_push_enabled", False) or user.pop("always_push_notify", False):
            modern_event["online_push_user_ids"].append(user_id)

        # We can calculate `mentioned` from the usermessage flags, so just remove it
        user.pop("mentioned", False)

    return (modern_event, user_dicts)


def process_notification(notice: Mapping[str, Any]) -> None:
    event: Mapping[str, Any] = notice["event"]
    users: Union[List[int], List[Mapping[str, Any]]] = notice["users"]
    start_time = time.perf_counter()

    if event["type"] == "message":
        if len(users) > 0 and isinstance(users[0], dict) and "stream_push_notify" in users[0]:
            # TODO/compatibility: Remove this whole block once one can no
            # longer directly upgrade directly from 4.x to 5.0-dev.
            modern_event, user_dicts = reformat_legacy_send_message_event(event, users)
            process_message_event(modern_event, user_dicts)
        else:
            process_message_event(event, cast(List[Mapping[str, Any]], users))
    elif event["type"] == "update_message":
        process_message_update_event(event, cast(List[Mapping[str, Any]], users))
    elif event["type"] == "delete_message":
        if len(users) > 0 and isinstance(users[0], dict):
            # do_delete_messages used to send events with users in
            # dict format {"id": <int>} This block is here for
            # compatibility with events in that format still in the
            # queue at the time of upgrade.
            #
            # TODO/compatibility: Remove this block once you can no
            # longer directly upgrade directly from 4.x to main.
            user_ids: List[int] = [user["id"] for user in cast(List[Mapping[str, Any]], users)]
        else:
            user_ids = cast(List[int], users)
        process_deletion_event(event, user_ids)
    elif event["type"] == "presence":
        process_presence_event(event, cast(List[int], users))
    elif event["type"] == "custom_profile_fields":
        process_custom_profile_fields_event(event, cast(List[int], users))
    elif event["type"] == "realm_user" and event["op"] == "add":
        process_realm_user_add_event(event, cast(List[int], users))
    elif event["type"] == "cleanup_queue":
        # cleanup_event_queue may generate this event to forward cleanup
        # requests to the right shard.
        assert isinstance(users[0], int)
        try:
            client = access_client_descriptor(users[0], event["queue_id"])
        except BadEventQueueIdError:
            logging.info(
                "Ignoring cleanup request for bad queue id %s (%d)", event["queue_id"], users[0]
            )
        else:
            client.cleanup()
    else:
        process_event(event, cast(List[int], users))
    logging.debug(
        "Tornado: Event %s for %s users took %sms",
        event["type"],
        len(users),
        int(1000 * (time.perf_counter() - start_time)),
    )


def get_wrapped_process_notification(queue_name: str) -> Callable[[List[Dict[str, Any]]], None]:
    def failure_processor(notice: Dict[str, Any]) -> None:
        logging.error(
            "Maximum retries exceeded for Tornado notice:%s\nStack trace:\n%s\n",
            notice,
            traceback.format_exc(),
        )

    def wrapped_process_notification(notices: List[Dict[str, Any]]) -> None:
        for notice in notices:
            try:
                process_notification(notice)
            except Exception:
                retry_event(queue_name, notice, failure_processor)

    return wrapped_process_notification

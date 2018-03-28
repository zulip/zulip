# See https://zulip.readthedocs.io/en/latest/subsystems/events-system.html for
# high-level documentation on how this system works.
from typing import cast, AbstractSet, Any, Callable, Dict, List, \
    Mapping, MutableMapping, Optional, Iterable, Sequence, Set, Text, Union
from mypy_extensions import TypedDict

from django.utils.translation import ugettext as _
from django.conf import settings
from collections import deque
import os
import time
import logging
import ujson
import requests
import atexit
import sys
import signal
import tornado.autoreload
import tornado.ioloop
import random
from zerver.models import UserProfile, Client
from zerver.decorator import cachify
from zerver.tornado.handlers import clear_handler_by_id, get_handler_by_id, \
    finish_handler, handler_stats_string
from zerver.lib.utils import statsd
from zerver.middleware import async_request_restart
from zerver.lib.message import MessageDict
from zerver.lib.narrow import build_narrow_filter
from zerver.lib.queue import queue_json_publish
from zerver.lib.request import JsonableError
from zerver.tornado.descriptors import clear_descriptor_by_handler_id, set_descriptor_by_handler_id
from zerver.tornado.exceptions import BadEventQueueIdError
import copy

requests_client = requests.Session()
for host in ['127.0.0.1', 'localhost']:
    if settings.TORNADO_SERVER and host in settings.TORNADO_SERVER:
        # This seems like the only working solution to ignore proxy in
        # requests library.
        requests_client.trust_env = False

# The idle timeout used to be a week, but we found that in that
# situation, queues from dead browser sessions would grow quite large
# due to the accumulation of message data in those queues.
IDLE_EVENT_QUEUE_TIMEOUT_SECS = 60 * 10
EVENT_QUEUE_GC_FREQ_MSECS = 1000 * 60 * 5

# Capped limit for how long a client can request an event queue
# to live
MAX_QUEUE_TIMEOUT_SECS = 7 * 24 * 60 * 60

# The heartbeats effectively act as a server-side timeout for
# get_events().  The actual timeout value is randomized for each
# client connection based on the below value.  We ensure that the
# maximum timeout value is 55 seconds, to deal with crappy home
# wireless routers that kill "inactive" http connections.
HEARTBEAT_MIN_FREQ_SECS = 45

class ClientDescriptor:
    def __init__(self,
                 user_profile_id: int,
                 user_profile_email: Text,
                 realm_id: int, event_queue: 'EventQueue',
                 event_types: Optional[Sequence[str]],
                 client_type_name: Text,
                 apply_markdown: bool=True,
                 client_gravatar: bool=True,
                 all_public_streams: bool=False,
                 lifespan_secs: int=0,
                 narrow: Iterable[Sequence[str]]=[]) -> None:
        # These objects are serialized on shutdown and restored on restart.
        # If fields are added or semantics are changed, temporary code must be
        # added to load_event_queues() to update the restored objects.
        # Additionally, the to_dict and from_dict methods must be updated
        self.user_profile_id = user_profile_id
        self.user_profile_email = user_profile_email
        self.realm_id = realm_id
        self.current_handler_id = None  # type: Optional[int]
        self.current_client_name = None  # type: Optional[Text]
        self.event_queue = event_queue
        self.queue_timeout = lifespan_secs
        self.event_types = event_types
        self.last_connection_time = time.time()
        self.apply_markdown = apply_markdown
        self.client_gravatar = client_gravatar
        self.all_public_streams = all_public_streams
        self.client_type_name = client_type_name
        self._timeout_handle = None  # type: Any # TODO: should be return type of ioloop.call_later
        self.narrow = narrow
        self.narrow_filter = build_narrow_filter(narrow)

        # Clamp queue_timeout to between minimum and maximum timeouts
        self.queue_timeout = max(IDLE_EVENT_QUEUE_TIMEOUT_SECS,
                                 min(self.queue_timeout, MAX_QUEUE_TIMEOUT_SECS))

    def to_dict(self) -> Dict[str, Any]:
        # If you add a new key to this dict, make sure you add appropriate
        # migration code in from_dict or load_event_queues to account for
        # loading event queues that lack that key.
        return dict(user_profile_id=self.user_profile_id,
                    user_profile_email=self.user_profile_email,
                    realm_id=self.realm_id,
                    event_queue=self.event_queue.to_dict(),
                    queue_timeout=self.queue_timeout,
                    event_types=self.event_types,
                    last_connection_time=self.last_connection_time,
                    apply_markdown=self.apply_markdown,
                    client_gravatar=self.client_gravatar,
                    all_public_streams=self.all_public_streams,
                    narrow=self.narrow,
                    client_type_name=self.client_type_name)

    def __repr__(self) -> str:
        return "ClientDescriptor<%s>" % (self.event_queue.id,)

    @classmethod
    def from_dict(cls, d: MutableMapping[str, Any]) -> 'ClientDescriptor':
        if 'user_profile_email' not in d:
            # Temporary migration for the addition of the new user_profile_email field
            from zerver.models import get_user_profile_by_id
            d['user_profile_email'] = get_user_profile_by_id(d['user_profile_id']).email
        if 'client_type' in d:
            # Temporary migration for the rename of client_type to client_type_name
            d['client_type_name'] = d['client_type']
        if 'client_gravatar' not in d:
            # Temporary migration for the addition of the client_gravatar field
            d['client_gravatar'] = False

        ret = cls(
            d['user_profile_id'],
            d['user_profile_email'],
            d['realm_id'],
            EventQueue.from_dict(d['event_queue']),
            d['event_types'],
            d['client_type_name'],
            d['apply_markdown'],
            d['client_gravatar'],
            d['all_public_streams'],
            d['queue_timeout'],
            d.get('narrow', [])
        )
        ret.last_connection_time = d['last_connection_time']
        return ret

    def prepare_for_pickling(self) -> None:
        self.current_handler_id = None
        self._timeout_handle = None

    def add_event(self, event: Dict[str, Any]) -> None:
        if self.current_handler_id is not None:
            handler = get_handler_by_id(self.current_handler_id)
            async_request_restart(handler._request)

        self.event_queue.push(event)
        self.finish_current_handler()

    def finish_current_handler(self) -> bool:
        if self.current_handler_id is not None:
            err_msg = "Got error finishing handler for queue %s" % (self.event_queue.id,)
            try:
                finish_handler(self.current_handler_id, self.event_queue.id,
                               self.event_queue.contents(), self.apply_markdown)
            except Exception:
                logging.exception(err_msg)
            finally:
                self.disconnect_handler()
                return True
        return False

    def accepts_event(self, event: Mapping[str, Any]) -> bool:
        if self.event_types is not None and event["type"] not in self.event_types:
            return False
        if event["type"] == "message":
            return self.narrow_filter(event)
        return True

    # TODO: Refactor so we don't need this function
    def accepts_messages(self) -> bool:
        return self.event_types is None or "message" in self.event_types

    def idle(self, now: float) -> bool:
        if not hasattr(self, 'queue_timeout'):
            self.queue_timeout = IDLE_EVENT_QUEUE_TIMEOUT_SECS

        return (self.current_handler_id is None and
                now - self.last_connection_time >= self.queue_timeout)

    def connect_handler(self, handler_id: int, client_name: Text) -> None:
        self.current_handler_id = handler_id
        self.current_client_name = client_name
        set_descriptor_by_handler_id(handler_id, self)
        self.last_connection_time = time.time()

        def timeout_callback() -> None:
            self._timeout_handle = None
            # All clients get heartbeat events
            self.add_event(dict(type='heartbeat'))
        ioloop = tornado.ioloop.IOLoop.instance()
        interval = HEARTBEAT_MIN_FREQ_SECS + random.randint(0, 10)
        if self.client_type_name != 'API: heartbeat test':
            self._timeout_handle = ioloop.call_later(interval, timeout_callback)

    def disconnect_handler(self, client_closed: bool=False) -> None:
        if self.current_handler_id:
            clear_descriptor_by_handler_id(self.current_handler_id, None)
            clear_handler_by_id(self.current_handler_id)
            if client_closed:
                logging.info("Client disconnected for queue %s (%s via %s)" %
                             (self.event_queue.id, self.user_profile_email,
                              self.current_client_name))
        self.current_handler_id = None
        self.current_client_name = None
        if self._timeout_handle is not None:
            ioloop = tornado.ioloop.IOLoop.instance()
            ioloop.remove_timeout(self._timeout_handle)
            self._timeout_handle = None

    def cleanup(self) -> None:
        # Before we can GC the event queue, we need to disconnect the
        # handler and notify the client (or connection server) so that
        # they can cleanup their own state related to the GC'd event
        # queue.  Finishing the handler before we GC ensures the
        # invariant that event queues are idle when passed to
        # `do_gc_event_queues` is preserved.
        self.finish_current_handler()
        do_gc_event_queues({self.event_queue.id}, {self.user_profile_id},
                           {self.realm_id})

def compute_full_event_type(event: Mapping[str, Any]) -> str:
    if event["type"] == "update_message_flags":
        if event["all"]:
            # Put the "all" case in its own category
            return "all_flags/%s/%s" % (event["flag"], event["operation"])
        return "flags/%s/%s" % (event["operation"], event["flag"])
    return event["type"]

class EventQueue:
    def __init__(self, id: str) -> None:
        self.queue = deque()  # type: ignore # Should be Deque[Dict[str, Any]], but Deque isn't available in Python 3.4
        self.next_event_id = 0  # type: int
        self.id = id  # type: str
        self.virtual_events = {}  # type: Dict[str, Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        # If you add a new key to this dict, make sure you add appropriate
        # migration code in from_dict or load_event_queues to account for
        # loading event queues that lack that key.
        return dict(id=self.id,
                    next_event_id=self.next_event_id,
                    queue=list(self.queue),
                    virtual_events=self.virtual_events)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'EventQueue':
        ret = cls(d['id'])
        ret.next_event_id = d['next_event_id']
        ret.queue = deque(d['queue'])
        ret.virtual_events = d.get("virtual_events", {})
        return ret

    def push(self, event: Dict[str, Any]) -> None:
        event['id'] = self.next_event_id
        self.next_event_id += 1
        full_event_type = compute_full_event_type(event)
        if (full_event_type in ["pointer", "restart"] or
                full_event_type.startswith("flags/")):
            if full_event_type not in self.virtual_events:
                self.virtual_events[full_event_type] = copy.deepcopy(event)
                return
            # Update the virtual event with the values from the event
            virtual_event = self.virtual_events[full_event_type]
            virtual_event["id"] = event["id"]
            if "timestamp" in event:
                virtual_event["timestamp"] = event["timestamp"]
            if full_event_type == "pointer":
                virtual_event["pointer"] = event["pointer"]
            elif full_event_type == "restart":
                virtual_event["server_generation"] = event["server_generation"]
            elif full_event_type.startswith("flags/"):
                virtual_event["messages"] += event["messages"]
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
        while len(self.queue) != 0 and self.queue[0]['id'] <= through_id:
            self.pop()

    def contents(self) -> List[Dict[str, Any]]:
        contents = []  # type: List[Dict[str, Any]]
        virtual_id_map = {}  # type: Dict[str, Dict[str, Any]]
        for event_type in self.virtual_events:
            virtual_id_map[self.virtual_events[event_type]["id"]] = self.virtual_events[event_type]
        virtual_ids = sorted(list(virtual_id_map.keys()))

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
        return contents

# maps queue ids to client descriptors
clients = {}  # type: Dict[str, ClientDescriptor]
# maps user id to list of client descriptors
user_clients = {}  # type: Dict[int, List[ClientDescriptor]]
# maps realm id to list of client descriptors with all_public_streams=True
realm_clients_all_streams = {}  # type: Dict[int, List[ClientDescriptor]]

# list of registered gc hooks.
# each one will be called with a user profile id, queue, and bool
# last_for_client that is true if this is the last queue pertaining
# to this user_profile_id
# that is about to be deleted
gc_hooks = []  # type: List[Callable[[int, ClientDescriptor, bool], None]]

next_queue_id = 0

def clear_client_event_queues_for_testing() -> None:
    assert(settings.TEST_SUITE)
    clients.clear()
    user_clients.clear()
    realm_clients_all_streams.clear()
    gc_hooks.clear()
    global next_queue_id
    next_queue_id = 0

def add_client_gc_hook(hook: Callable[[int, ClientDescriptor, bool], None]) -> None:
    gc_hooks.append(hook)

def get_client_descriptor(queue_id: str) -> ClientDescriptor:
    return clients.get(queue_id)

def get_client_descriptors_for_user(user_profile_id: int) -> List[ClientDescriptor]:
    return user_clients.get(user_profile_id, [])

def get_client_descriptors_for_realm_all_streams(realm_id: int) -> List[ClientDescriptor]:
    return realm_clients_all_streams.get(realm_id, [])

def add_to_client_dicts(client: ClientDescriptor) -> None:
    user_clients.setdefault(client.user_profile_id, []).append(client)
    if client.all_public_streams or client.narrow != []:
        realm_clients_all_streams.setdefault(client.realm_id, []).append(client)

def allocate_client_descriptor(new_queue_data: MutableMapping[str, Any]) -> ClientDescriptor:
    global next_queue_id
    queue_id = str(settings.SERVER_GENERATION) + ':' + str(next_queue_id)
    next_queue_id += 1
    new_queue_data["event_queue"] = EventQueue(queue_id).to_dict()
    client = ClientDescriptor.from_dict(new_queue_data)
    clients[queue_id] = client
    add_to_client_dicts(client)
    return client

def do_gc_event_queues(to_remove: AbstractSet[str], affected_users: AbstractSet[int],
                       affected_realms: AbstractSet[int]) -> None:
    def filter_client_dict(client_dict: MutableMapping[int, List[ClientDescriptor]], key: int) -> None:
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
            cb(clients[id].user_profile_id, clients[id], clients[id].user_profile_id not in user_clients)
        del clients[id]

def gc_event_queues() -> None:
    start = time.time()
    to_remove = set()  # type: Set[str]
    affected_users = set()  # type: Set[int]
    affected_realms = set()  # type: Set[int]
    for (id, client) in clients.items():
        if client.idle(start):
            to_remove.add(id)
            affected_users.add(client.user_profile_id)
            affected_realms.add(client.realm_id)

    # We don't need to call e.g. finish_current_handler on the clients
    # being removed because they are guaranteed to be idle and thus
    # not have a current handler.
    do_gc_event_queues(to_remove, affected_users, affected_realms)

    if settings.PRODUCTION:
        logging.info(('Tornado removed %d idle event queues owned by %d users in %.3fs.' +
                      '  Now %d active queues, %s')
                     % (len(to_remove), len(affected_users), time.time() - start,
                        len(clients), handler_stats_string()))
    statsd.gauge('tornado.active_queues', len(clients))
    statsd.gauge('tornado.active_users', len(user_clients))

def dump_event_queues() -> None:
    start = time.time()

    with open(settings.JSON_PERSISTENT_QUEUE_FILENAME, "w") as stored_queues:
        ujson.dump([(qid, client.to_dict()) for (qid, client) in clients.items()],
                   stored_queues)

    logging.info('Tornado dumped %d event queues in %.3fs'
                 % (len(clients), time.time() - start))

def load_event_queues() -> None:
    global clients
    start = time.time()

    # ujson chokes on bad input pretty easily.  We separate out the actual
    # file reading from the loading so that we don't silently fail if we get
    # bad input.
    try:
        with open(settings.JSON_PERSISTENT_QUEUE_FILENAME, "r") as stored_queues:
            json_data = stored_queues.read()
        try:
            clients = dict((qid, ClientDescriptor.from_dict(client))
                           for (qid, client) in ujson.loads(json_data))
        except Exception:
            logging.exception("Could not deserialize event queues")
    except (IOError, EOFError):
        pass

    for client in clients.values():
        # Put code for migrations due to event queue data format changes here

        add_to_client_dicts(client)

    logging.info('Tornado loaded %d event queues in %.3fs'
                 % (len(clients), time.time() - start))

def send_restart_events(immediate: bool=False) -> None:
    event = dict(type='restart', server_generation=settings.SERVER_GENERATION)  # type: Dict[str, Any]
    if immediate:
        event['immediate'] = True
    for client in clients.values():
        if client.accepts_event(event):
            client.add_event(event.copy())

def setup_event_queue() -> None:
    if not settings.TEST_SUITE:
        load_event_queues()
        atexit.register(dump_event_queues)
        # Make sure we dump event queues even if we exit via signal
        signal.signal(signal.SIGTERM, lambda signum, stack: sys.exit(1))
        tornado.autoreload.add_reload_hook(dump_event_queues)

    try:
        os.rename(settings.JSON_PERSISTENT_QUEUE_FILENAME, "/var/tmp/event_queues.json.last")
    except OSError:
        pass

    # Set up event queue garbage collection
    ioloop = tornado.ioloop.IOLoop.instance()
    pc = tornado.ioloop.PeriodicCallback(gc_event_queues,
                                         EVENT_QUEUE_GC_FREQ_MSECS, ioloop)
    pc.start()

    send_restart_events(immediate=settings.DEVELOPMENT)

def fetch_events(query: Mapping[str, Any]) -> Dict[str, Any]:
    queue_id = query["queue_id"]  # type: str
    dont_block = query["dont_block"]  # type: bool
    last_event_id = query["last_event_id"]  # type: int
    user_profile_id = query["user_profile_id"]  # type: int
    new_queue_data = query.get("new_queue_data")  # type: Optional[MutableMapping[str, Any]]
    user_profile_email = query["user_profile_email"]  # type: Text
    client_type_name = query["client_type_name"]  # type: Text
    handler_id = query["handler_id"]  # type: int

    try:
        was_connected = False
        orig_queue_id = queue_id
        extra_log_data = ""
        if queue_id is None:
            if dont_block:
                client = allocate_client_descriptor(new_queue_data)
                queue_id = client.event_queue.id
            else:
                raise JsonableError(_("Missing 'queue_id' argument"))
        else:
            if last_event_id is None:
                raise JsonableError(_("Missing 'last_event_id' argument"))
            client = get_client_descriptor(queue_id)
            if client is None:
                raise BadEventQueueIdError(queue_id)
            if user_profile_id != client.user_profile_id:
                raise JsonableError(_("You are not authorized to get events from this queue"))
            client.event_queue.prune(last_event_id)
            was_connected = client.finish_current_handler()

        if not client.event_queue.empty() or dont_block:
            response = dict(events=client.event_queue.contents(),
                            handler_id=handler_id)  # type: Dict[str, Any]
            if orig_queue_id is None:
                response['queue_id'] = queue_id
            if len(response["events"]) == 1:
                extra_log_data = "[%s/%s/%s]" % (queue_id, len(response["events"]),
                                                 response["events"][0]["type"])
            else:
                extra_log_data = "[%s/%s]" % (queue_id, len(response["events"]))
            if was_connected:
                extra_log_data += " [was connected]"
            return dict(type="response", response=response, extra_log_data=extra_log_data)

        # After this point, dont_block=False, the queue is empty, and we
        # have a pre-existing queue, so we wait for new events.
        if was_connected:
            logging.info("Disconnected handler for queue %s (%s/%s)" % (queue_id, user_profile_email,
                                                                        client_type_name))
    except JsonableError as e:
        return dict(type="error", exception=e)

    client.connect_handler(handler_id, client_type_name)
    return dict(type="async")

# The following functions are called from Django

# Workaround to support the Python-requests 1.0 transition of .json
# from a property to a function
requests_json_is_function = callable(requests.Response.json)
def extract_json_response(resp: requests.Response) -> Dict[str, Any]:
    if requests_json_is_function:
        return resp.json()
    else:
        return resp.json  # type: ignore # mypy trusts the stub, not the runtime type checking of this fn

def request_event_queue(user_profile: UserProfile, user_client: Client, apply_markdown: bool,
                        client_gravatar: bool, queue_lifespan_secs: int,
                        event_types: Optional[Iterable[str]]=None,
                        all_public_streams: bool=False,
                        narrow: Iterable[Sequence[Text]]=[]) -> Optional[str]:
    if settings.TORNADO_SERVER:
        req = {'dont_block': 'true',
               'apply_markdown': ujson.dumps(apply_markdown),
               'client_gravatar': ujson.dumps(client_gravatar),
               'all_public_streams': ujson.dumps(all_public_streams),
               'client': 'internal',
               'user_client': user_client.name,
               'narrow': ujson.dumps(narrow),
               'lifespan_secs': queue_lifespan_secs}
        if event_types is not None:
            req['event_types'] = ujson.dumps(event_types)

        try:
            resp = requests_client.get(settings.TORNADO_SERVER + '/api/v1/events',
                                       auth=requests.auth.HTTPBasicAuth(
                                           user_profile.email, user_profile.api_key),
                                       params=req)
        except requests.adapters.ConnectionError:
            logging.error('Tornado server does not seem to be running, check %s '
                          'and %s for more information.' %
                          (settings.ERROR_FILE_LOG_PATH, "tornado.log"))
            raise requests.adapters.ConnectionError(
                "Django cannot connect to Tornado server (%s); try restarting" %
                (settings.TORNADO_SERVER))

        resp.raise_for_status()

        return extract_json_response(resp)['queue_id']

    return None

def get_user_events(user_profile: UserProfile, queue_id: str, last_event_id: int) -> List[Dict[Any, Any]]:
    if settings.TORNADO_SERVER:
        resp = requests_client.get(settings.TORNADO_SERVER + '/api/v1/events',
                                   auth=requests.auth.HTTPBasicAuth(
                                       user_profile.email, user_profile.api_key),
                                   params={'queue_id': queue_id,
                                           'last_event_id': last_event_id,
                                           'dont_block': 'true',
                                           'client': 'internal'})

        resp.raise_for_status()

        return extract_json_response(resp)['events']
    return []

# Send email notifications to idle users
# after they are idle for 1 hour
NOTIFY_AFTER_IDLE_HOURS = 1
def build_offline_notification(user_profile_id: int, message_id: int) -> Dict[str, Any]:
    return {"user_profile_id": user_profile_id,
            "message_id": message_id,
            "timestamp": time.time()}

def missedmessage_hook(user_profile_id: int, client: ClientDescriptor, last_for_client: bool) -> None:
    """The receiver_is_off_zulip logic used to determine whether a user
    has no active client suffers from a somewhat fundamental race
    condition.  If the client is no longer on the Internet,
    receiver_is_off_zulip will still return true for
    IDLE_EVENT_QUEUE_TIMEOUT_SECS, until the queue is
    garbage-collected.  This would cause us to reliably miss
    push/email notifying users for messages arriving during the
    IDLE_EVENT_QUEUE_TIMEOUT_SECS after they suspend their laptop (for
    example).  We address this by, when the queue is garbage-collected
    at the end of those 10 minutes, checking to see if it's the last
    one, and if so, potentially triggering notifications to the user
    at that time, resulting in at most a IDLE_EVENT_QUEUE_TIMEOUT_SECS
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

    for event in client.event_queue.contents():
        if event['type'] != 'message':
            continue
        assert 'flags' in event

        flags = event.get('flags')

        mentioned = 'mentioned' in flags and 'read' not in flags
        private_message = event['message']['type'] == 'private'
        # stream_push_notify is set in process_message_event.
        stream_push_notify = event.get('stream_push_notify', False)

        stream_name = None
        if not private_message:
            stream_name = event['message']['display_recipient']

        # Since one is by definition idle, we don't need to check always_push_notify
        always_push_notify = False
        # Since we just GC'd the last event queue, the user is definitely idle.
        idle = True

        message_id = event['message']['id']
        # Pass on the information on whether a push or email notification was already sent.
        already_notified = dict(
            push_notified = event.get("push_notified", False),
            email_notified = event.get("email_notified", False),
        )
        maybe_enqueue_notifications(user_profile_id, message_id, private_message, mentioned,
                                    stream_push_notify, stream_name, always_push_notify, idle,
                                    already_notified)

def receiver_is_off_zulip(user_profile_id: int) -> bool:
    # If a user has no message-receiving event queues, they've got no open zulip
    # session so we notify them
    all_client_descriptors = get_client_descriptors_for_user(user_profile_id)
    message_event_queues = [client for client in all_client_descriptors if client.accepts_messages()]
    off_zulip = len(message_event_queues) == 0
    return off_zulip

def maybe_enqueue_notifications(user_profile_id: int, message_id: int, private_message: bool,
                                mentioned: bool, stream_push_notify: bool, stream_name: Optional[str],
                                always_push_notify: bool, idle: bool,
                                already_notified: Dict[str, bool]) -> Dict[str, bool]:
    """This function has a complete unit test suite in
    `test_enqueue_notifications` that should be expanded as we add
    more features here."""
    notified = dict()  # type: Dict[str, bool]

    if (idle or always_push_notify) and (private_message or mentioned or stream_push_notify):
        notice = build_offline_notification(user_profile_id, message_id)
        if private_message:
            notice['trigger'] = 'private_message'
        elif mentioned:
            notice['trigger'] = 'mentioned'
        elif stream_push_notify:
            notice['trigger'] = 'stream_push_notify'
        else:
            raise AssertionError("Unknown notification trigger!")
        notice['stream_name'] = stream_name
        if not already_notified.get("push_notified"):
            queue_json_publish("missedmessage_mobile_notifications", notice, lambda notice: None)
            notified['push_notified'] = True

    # Send missed_message emails if a private message or a
    # mention.  Eventually, we'll add settings to allow email
    # notifications to match the model of push notifications
    # above.
    if idle and (private_message or mentioned):
        # We require RabbitMQ to do this, as we can't call the email handler
        # from the Tornado process. So if there's no rabbitmq support do nothing
        if not already_notified.get("email_notified"):
            queue_json_publish("missedmessage_emails", notice, lambda notice: None)
            notified['email_notified'] = True

    return notified

ClientInfo = TypedDict('ClientInfo', {
    'client': ClientDescriptor,
    'flags': Optional[Iterable[str]],
    'is_sender': bool,
})

def get_client_info_for_message_event(event_template: Mapping[str, Any],
                                      users: Iterable[Mapping[str, Any]]) -> Dict[str, ClientInfo]:

    '''
    Return client info for all the clients interested in a message.
    This basically includes clients for users who are recipients
    of the message, with some nuances for bots that auto-subscribe
    to all streams, plus users who may be mentioned, etc.
    '''

    send_to_clients = {}  # type: Dict[str, ClientInfo]

    sender_queue_id = event_template.get('sender_queue_id', None)  # type: Optional[str]

    def is_sender_client(client: ClientDescriptor) -> bool:
        return (sender_queue_id is not None) and client.event_queue.id == sender_queue_id

    # If we're on a public stream, look for clients (typically belonging to
    # bots) that are registered to get events for ALL streams.
    if 'stream_name' in event_template and not event_template.get("invite_only"):
        realm_id = event_template['realm_id']
        for client in get_client_descriptors_for_realm_all_streams(realm_id):
            send_to_clients[client.event_queue.id] = dict(
                client=client,
                flags=[],
                is_sender=is_sender_client(client)
            )

    for user_data in users:
        user_profile_id = user_data['id']  # type: int
        flags = user_data.get('flags', [])  # type: Iterable[str]

        for client in get_client_descriptors_for_user(user_profile_id):
            send_to_clients[client.event_queue.id] = dict(
                client=client,
                flags=flags,
                is_sender=is_sender_client(client)
            )

    return send_to_clients


def process_message_event(event_template: Mapping[str, Any], users: Iterable[Mapping[str, Any]]) -> None:
    send_to_clients = get_client_info_for_message_event(event_template, users)

    presence_idle_user_ids = set(event_template.get('presence_idle_user_ids', []))
    wide_dict = event_template['message_dict']  # type: Dict[str, Any]

    sender_id = wide_dict['sender_id']  # type: int
    message_id = wide_dict['id']  # type: int
    message_type = wide_dict['type']  # type: str
    sending_client = wide_dict['client']  # type: Text

    @cachify
    def get_client_payload(apply_markdown: bool, client_gravatar: bool) -> Dict[str, Any]:
        dct = copy.deepcopy(wide_dict)
        MessageDict.finalize_payload(dct, apply_markdown, client_gravatar)
        return dct

    # Extra user-specific data to include
    extra_user_data = {}  # type: Dict[int, Any]

    for user_data in users:
        user_profile_id = user_data['id']  # type: int
        flags = user_data.get('flags', [])  # type: Iterable[str]

        # If the recipient was offline and the message was a single or group PM to them
        # or they were @-notified potentially notify more immediately
        private_message = message_type == "private" and user_profile_id != sender_id
        mentioned = 'mentioned' in flags and 'read' not in flags
        stream_push_notify = user_data.get('stream_push_notify', False)

        # We first check if a message is potentially mentionable,
        # since receiver_is_off_zulip is somewhat expensive.
        if private_message or mentioned or stream_push_notify:
            idle = receiver_is_off_zulip(user_profile_id) or (user_profile_id in presence_idle_user_ids)
            always_push_notify = user_data.get('always_push_notify', False)
            stream_name = event_template.get('stream_name')
            result = maybe_enqueue_notifications(user_profile_id, message_id, private_message,
                                                 mentioned, stream_push_notify, stream_name,
                                                 always_push_notify, idle, {})
            result['stream_push_notify'] = stream_push_notify
            extra_user_data[user_profile_id] = result

    for client_data in send_to_clients.values():
        client = client_data['client']
        flags = client_data['flags']
        is_sender = client_data.get('is_sender', False)  # type: bool
        extra_data = extra_user_data.get(client.user_profile_id, None)  # type: Optional[Mapping[str, bool]]

        if not client.accepts_messages():
            # The actual check is the accepts_event() check below;
            # this line is just an optimization to avoid copying
            # message data unnecessarily
            continue

        message_dict = get_client_payload(client.apply_markdown, client.client_gravatar)

        # Make sure Zephyr mirroring bots know whether stream is invite-only
        if "mirror" in client.client_type_name and event_template.get("invite_only"):
            message_dict = message_dict.copy()
            message_dict["invite_only_stream"] = True

        user_event = dict(type='message', message=message_dict, flags=flags)  # type: Dict[str, Any]
        if extra_data is not None:
            user_event.update(extra_data)

        if is_sender:
            local_message_id = event_template.get('local_id', None)
            if local_message_id is not None:
                user_event["local_message_id"] = local_message_id

        if not client.accepts_event(user_event):
            continue

        # The below prevents (Zephyr) mirroring loops.
        if ('mirror' in sending_client and
                sending_client.lower() == client.client_type_name.lower()):
            continue
        client.add_event(user_event)

def process_event(event: Mapping[str, Any], users: Iterable[int]) -> None:
    for user_profile_id in users:
        for client in get_client_descriptors_for_user(user_profile_id):
            if client.accepts_event(event):
                client.add_event(dict(event))

def process_userdata_event(event_template: Mapping[str, Any], users: Iterable[Mapping[str, Any]]) -> None:
    for user_data in users:
        user_profile_id = user_data['id']
        user_event = dict(event_template)  # shallow copy, but deep enough for our needs
        for key in user_data.keys():
            if key != "id":
                user_event[key] = user_data[key]

        for client in get_client_descriptors_for_user(user_profile_id):
            if client.accepts_event(user_event):
                client.add_event(user_event)

def process_message_update_event(event_template: Mapping[str, Any],
                                 users: Iterable[Mapping[str, Any]]) -> None:
    prior_mention_user_ids = set(event_template.get('prior_mention_user_ids', []))
    mention_user_ids = set(event_template.get('mention_user_ids', []))
    presence_idle_user_ids = set(event_template.get('presence_idle_user_ids', []))
    stream_push_user_ids = set(event_template.get('stream_push_user_ids', []))
    push_notify_user_ids = set(event_template.get('push_notify_user_ids', []))

    stream_name = event_template.get('stream_name')
    message_id = event_template['message_id']

    for user_data in users:
        user_profile_id = user_data['id']
        user_event = dict(event_template)  # shallow copy, but deep enough for our needs
        for key in user_data.keys():
            if key != "id":
                user_event[key] = user_data[key]

        maybe_enqueue_notifications_for_message_update(
            user_profile_id=user_profile_id,
            message_id=message_id,
            stream_name=stream_name,
            prior_mention_user_ids=prior_mention_user_ids,
            mention_user_ids=mention_user_ids,
            presence_idle_user_ids=presence_idle_user_ids,
            stream_push_user_ids=stream_push_user_ids,
            push_notify_user_ids=push_notify_user_ids,
        )

        for client in get_client_descriptors_for_user(user_profile_id):
            if client.accepts_event(user_event):
                client.add_event(user_event)

def maybe_enqueue_notifications_for_message_update(user_profile_id: UserProfile,
                                                   message_id: int,
                                                   stream_name: str,
                                                   prior_mention_user_ids: Set[int],
                                                   mention_user_ids: Set[int],
                                                   presence_idle_user_ids: Set[int],
                                                   stream_push_user_ids: Set[int],
                                                   push_notify_user_ids: Set[int]) -> None:
    private_message = (stream_name is None)

    if private_message:
        # We don't do offline notifications for PMs, because
        # we already notified the user of the original message
        return

    if (user_profile_id in prior_mention_user_ids):
        # Don't spam people with duplicate mentions.  This is
        # especially important considering that most message
        # edits are simple typo corrections.
        return

    stream_push_notify = (user_profile_id in stream_push_user_ids)

    if stream_push_notify:
        # Currently we assume that if this flag is set to True, then
        # the user already was notified about the earlier message,
        # so we short circuit.  We may handle this more rigorously
        # in the future by looking at something like an AlreadyNotified
        # model.
        return

    # We can have newly mentioned people in an updated message.
    mentioned = (user_profile_id in mention_user_ids)

    always_push_notify = user_profile_id in push_notify_user_ids

    idle = (user_profile_id in presence_idle_user_ids) or \
        receiver_is_off_zulip(user_profile_id)

    maybe_enqueue_notifications(
        user_profile_id=user_profile_id,
        message_id=message_id,
        private_message=private_message,
        mentioned=mentioned,
        stream_push_notify=stream_push_notify,
        stream_name=stream_name,
        always_push_notify=always_push_notify,
        idle=idle,
        already_notified={},
    )

def process_notification(notice: Mapping[str, Any]) -> None:
    event = notice['event']  # type: Mapping[str, Any]
    users = notice['users']  # type: Union[List[int], List[Mapping[str, Any]]]
    start_time = time.time()
    if event['type'] == "message":
        process_message_event(event, cast(Iterable[Mapping[str, Any]], users))
    elif event['type'] == "update_message":
        process_message_update_event(event, cast(Iterable[Mapping[str, Any]], users))
    elif event['type'] == "delete_message":
        process_userdata_event(event, cast(Iterable[Mapping[str, Any]], users))
    else:
        process_event(event, cast(Iterable[int], users))
    logging.debug("Tornado: Event %s for %s users took %sms" % (
        event['type'], len(users), int(1000 * (time.time() - start_time))))

# Runs in the Django process to send a notification to Tornado.
#
# We use JSON rather than bare form parameters, so that we can represent
# different types and for compatibility with non-HTTP transports.

def send_notification_http(data: Mapping[str, Any]) -> None:
    if settings.TORNADO_SERVER and not settings.RUNNING_INSIDE_TORNADO:
        requests_client.post(settings.TORNADO_SERVER + '/notify_tornado', data=dict(
            data   = ujson.dumps(data),
            secret = settings.SHARED_SECRET))
    else:
        process_notification(data)

def send_notification(data: Dict[str, Any]) -> None:
    queue_json_publish("notify_tornado", data, send_notification_http)

def send_event(event: Mapping[str, Any],
               users: Union[Iterable[int], Iterable[Mapping[str, Any]]]) -> None:
    """`users` is a list of user IDs, or in the case of `message` type
    events, a list of dicts describing the users and metadata about
    the user/message pair."""
    queue_json_publish("notify_tornado",
                       dict(event=event, users=users),
                       send_notification_http)

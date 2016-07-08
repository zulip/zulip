from __future__ import absolute_import
from typing import cast, AbstractSet, Any, Optional, Iterable, Sequence, Mapping, MutableMapping, Callable, Union

from django.utils.translation import ugettext as _
from django.conf import settings
from django.utils.timezone import now
from collections import deque
import datetime
import os
import time
import socket
import logging
import ujson
import requests
import atexit
import sys
import signal
import tornado
import tornado.autoreload
import random
import traceback
from zerver.models import UserProfile, Client
from zerver.decorator import RespondAsynchronously
from zerver.lib.cache import cache_get_many, \
    user_profile_by_id_cache_key, cache_save_user_profile, cache_with_key
from zerver.lib.handlers import clear_handler_by_id, get_handler_by_id, \
    finish_handler, handler_stats_string
from zerver.lib.utils import statsd
from zerver.middleware import async_request_restart
from zerver.lib.narrow import build_narrow_filter
from zerver.lib.queue import queue_json_publish
from zerver.lib.request import JsonableError
from zerver.lib.timestamp import timestamp_to_datetime
import copy
import six
from six import text_type

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

class ClientDescriptor(object):
    def __init__(self, user_profile_id, user_profile_email, realm_id, event_queue,
                 event_types, client_type_name, apply_markdown=True,
                 all_public_streams=False, lifespan_secs=0, narrow=[]):
        # type: (int, text_type, int, EventQueue, Optional[Sequence[str]], text_type, bool, bool, int, Iterable[Sequence[text_type]]) -> None
        # These objects are serialized on shutdown and restored on restart.
        # If fields are added or semantics are changed, temporary code must be
        # added to load_event_queues() to update the restored objects.
        # Additionally, the to_dict and from_dict methods must be updated
        self.user_profile_id = user_profile_id
        self.user_profile_email = user_profile_email
        self.realm_id = realm_id
        self.current_handler_id = None # type: Optional[int]
        self.current_client_name = None # type: Optional[text_type]
        self.event_queue = event_queue
        self.queue_timeout = lifespan_secs
        self.event_types = event_types
        self.last_connection_time = time.time()
        self.apply_markdown = apply_markdown
        self.all_public_streams = all_public_streams
        self.client_type_name = client_type_name
        self._timeout_handle = None # type: Any # TODO: should be return type of ioloop.add_timeout
        self.narrow = narrow
        self.narrow_filter = build_narrow_filter(narrow)

        # Clamp queue_timeout to between minimum and maximum timeouts
        self.queue_timeout = max(IDLE_EVENT_QUEUE_TIMEOUT_SECS, min(self.queue_timeout, MAX_QUEUE_TIMEOUT_SECS))

    def to_dict(self):
        # type: () -> Dict[str, Any]
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
                    all_public_streams=self.all_public_streams,
                    narrow=self.narrow,
                    client_type_name=self.client_type_name)

    def __repr__(self):
        # type: () -> str
        return "ClientDescriptor<%s>" % (self.event_queue.id,)

    @classmethod
    def from_dict(cls, d):
        # type: (MutableMapping[str, Any]) -> ClientDescriptor
        if 'user_profile_email' not in d:
            # Temporary migration for the addition of the new user_profile_email field
            from zerver.models import get_user_profile_by_id
            d['user_profile_email'] = get_user_profile_by_id(d['user_profile_id']).email
        if 'client_type' in d:
            # Temporary migration for the rename of client_type to client_type_name
            d['client_type_name'] = d['client_type']
        ret = cls(d['user_profile_id'], d['user_profile_email'], d['realm_id'],
                  EventQueue.from_dict(d['event_queue']), d['event_types'],
                  d['client_type_name'], d['apply_markdown'], d['all_public_streams'],
                  d['queue_timeout'], d.get('narrow', []))
        ret.last_connection_time = d['last_connection_time']
        return ret

    def prepare_for_pickling(self):
        # type: () -> None
        self.current_handler_id = None
        self._timeout_handle = None

    def add_event(self, event):
        # type: (Dict[str, Any]) -> None
        if self.current_handler_id is not None:
            handler = get_handler_by_id(self.current_handler_id)
            async_request_restart(handler._request)

        self.event_queue.push(event)
        self.finish_current_handler()

    def finish_current_handler(self, need_timeout=False):
        # type: (bool) -> bool
        if self.current_handler_id is not None:
            err_msg = "Got error finishing handler for queue %s" % (self.event_queue.id,)
            try:
                finish_handler(self.current_handler_id, self.event_queue.id,
                               self.event_queue.contents(), self.apply_markdown)
            except Exception:
                logging.exception(err_msg)
            finally:
                self.disconnect_handler(need_timeout=need_timeout)
                return True
        return False

    def accepts_event(self, event):
        # type: (Mapping[str, Any]) -> bool
        if self.event_types is not None and event["type"] not in self.event_types:
            return False
        if event["type"] == "message":
            return self.narrow_filter(event)
        return True

    # TODO: Refactor so we don't need this function
    def accepts_messages(self):
        # type: () -> bool
        return self.event_types is None or "message" in self.event_types

    def idle(self, now):
        # type: (float) -> bool
        if not hasattr(self, 'queue_timeout'):
            self.queue_timeout = IDLE_EVENT_QUEUE_TIMEOUT_SECS

        return (self.current_handler_id is None
                and now - self.last_connection_time >= self.queue_timeout)

    def connect_handler(self, handler_id, client_name):
        # type: (int, text_type) -> None
        self.current_handler_id = handler_id
        self.current_client_name = client_name
        set_descriptor_by_handler_id(handler_id, self)
        self.last_connection_time = time.time()
        def timeout_callback():
            # type: () -> None
            self._timeout_handle = None
            # All clients get heartbeat events
            self.add_event(dict(type='heartbeat'))
        ioloop = tornado.ioloop.IOLoop.instance()
        heartbeat_time = time.time() + HEARTBEAT_MIN_FREQ_SECS + random.randint(0, 10)
        if self.client_type_name != 'API: heartbeat test':
            self._timeout_handle = ioloop.add_timeout(heartbeat_time, timeout_callback)

    def disconnect_handler(self, client_closed=False, need_timeout=True):
        # type: (bool, bool) -> None
        if self.current_handler_id:
            clear_descriptor_by_handler_id(self.current_handler_id, None)
            clear_handler_by_id(self.current_handler_id)
            if client_closed:
                logging.info("Client disconnected for queue %s (%s via %s)" %
                             (self.event_queue.id, self.user_profile_email,
                              self.current_client_name))
        self.current_handler_id = None
        self.current_client_name = None
        if need_timeout and self._timeout_handle is not None:
            ioloop = tornado.ioloop.IOLoop.instance()
            ioloop.remove_timeout(self._timeout_handle)
            self._timeout_handle = None

    def cleanup(self):
        # type: () -> None
        # Before we can GC the event queue, we need to disconnect the
        # handler and notify the client (or connection server) so that
        # they can cleanup their own state related to the GC'd event
        # queue.  Finishing the handler before we GC ensures the
        # invariant that event queues are idle when passed to
        # `do_gc_event_queues` is preserved.
        self.finish_current_handler(need_timeout=False)
        do_gc_event_queues({self.event_queue.id}, {self.user_profile_id},
                           {self.realm_id})

descriptors_by_handler_id = {} # type: Dict[int, ClientDescriptor]

def get_descriptor_by_handler_id(handler_id):
    # type: (int) -> ClientDescriptor
    return descriptors_by_handler_id.get(handler_id)

def set_descriptor_by_handler_id(handler_id, client_descriptor):
    # type: (int, ClientDescriptor) -> None
    descriptors_by_handler_id[handler_id] = client_descriptor

def clear_descriptor_by_handler_id(handler_id, client_descriptor):
    # type: (int, Optional[ClientDescriptor]) -> None
    del descriptors_by_handler_id[handler_id]

def compute_full_event_type(event):
    # type: (Mapping[str, Any]) -> str
    if event["type"] == "update_message_flags":
        if event["all"]:
            # Put the "all" case in its own category
            return "all_flags/%s/%s" % (event["flag"], event["operation"])
        return "flags/%s/%s" % (event["operation"], event["flag"])
    return event["type"]

class EventQueue(object):
    def __init__(self, id):
        # type: (str) -> None
        self.queue = deque() # type: deque[Dict[str, Any]]
        self.next_event_id = 0 # type: int
        self.id = id # type: str
        self.virtual_events = {} # type: Dict[str, Dict[str, Any]]

    def to_dict(self):
        # type: () -> Dict[str, Any]
        # If you add a new key to this dict, make sure you add appropriate
        # migration code in from_dict or load_event_queues to account for
        # loading event queues that lack that key.
        return dict(id=self.id,
                    next_event_id=self.next_event_id,
                    queue=list(self.queue),
                    virtual_events=self.virtual_events)

    @classmethod
    def from_dict(cls, d):
        # type: (Dict[str, Any]) -> EventQueue
        ret = cls(d['id'])
        ret.next_event_id = d['next_event_id']
        ret.queue = deque(d['queue'])
        ret.virtual_events = d.get("virtual_events", {})
        return ret

    def push(self, event):
        # type: (Dict[str, Any]) -> None
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
    def pop(self):
        # type: () -> Dict[str, Any]
        return self.queue.popleft()

    def empty(self):
        # type: () -> bool
        return len(self.queue) == 0 and len(self.virtual_events) == 0

    # See the comment on pop; that applies here as well
    def prune(self, through_id):
        # type: (int) -> None
        while len(self.queue) != 0 and self.queue[0]['id'] <= through_id:
            self.pop()

    def contents(self):
        # type: () -> List[Dict[str, Any]]
        contents = [] # type: List[Dict[str, Any]]
        virtual_id_map = {} # type: Dict[str, Dict[str, Any]]
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
clients = {} # type: Dict[str, ClientDescriptor]
# maps user id to list of client descriptors
user_clients = {} # type: Dict[int, List[ClientDescriptor]]
# maps realm id to list of client descriptors with all_public_streams=True
realm_clients_all_streams = {} # type: Dict[int, List[ClientDescriptor]]

# list of registered gc hooks.
# each one will be called with a user profile id, queue, and bool
# last_for_client that is true if this is the last queue pertaining
# to this user_profile_id
# that is about to be deleted
gc_hooks = [] # type: List[Callable[[int, ClientDescriptor, bool], None]]

next_queue_id = 0

def add_client_gc_hook(hook):
    # type: (Callable[[int, ClientDescriptor, bool], None]) -> None
    gc_hooks.append(hook)

def get_client_descriptor(queue_id):
    # type: (str) -> ClientDescriptor
    return clients.get(queue_id)

def get_client_descriptors_for_user(user_profile_id):
    # type: (int) -> List[ClientDescriptor]
    return user_clients.get(user_profile_id, [])

def get_client_descriptors_for_realm_all_streams(realm_id):
    # type: (int) -> List[ClientDescriptor]
    return realm_clients_all_streams.get(realm_id, [])

def add_to_client_dicts(client):
    # type: (ClientDescriptor) -> None
    user_clients.setdefault(client.user_profile_id, []).append(client)
    if client.all_public_streams or client.narrow != []:
        realm_clients_all_streams.setdefault(client.realm_id, []).append(client)

def allocate_client_descriptor(new_queue_data):
    # type: (MutableMapping[str, Any]) -> ClientDescriptor
    global next_queue_id
    queue_id = str(settings.SERVER_GENERATION) + ':' + str(next_queue_id)
    next_queue_id += 1
    new_queue_data["event_queue"] = EventQueue(queue_id).to_dict()
    client = ClientDescriptor.from_dict(new_queue_data)
    clients[queue_id] = client
    add_to_client_dicts(client)
    return client

def do_gc_event_queues(to_remove, affected_users, affected_realms):
    # type: (AbstractSet[str], AbstractSet[int], AbstractSet[int]) -> None
    def filter_client_dict(client_dict, key):
        # type: (MutableMapping[int, List[ClientDescriptor]], int) -> None
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

def gc_event_queues():
    # type: () -> None
    start = time.time()
    to_remove = set() # type: Set[str]
    affected_users = set() # type: Set[int]
    affected_realms = set() # type: Set[int]
    for (id, client) in six.iteritems(clients):
        if client.idle(start):
            to_remove.add(id)
            affected_users.add(client.user_profile_id)
            affected_realms.add(client.realm_id)

    # We don't need to call e.g. finish_current_handler on the clients
    # being removed because they are guaranteed to be idle and thus
    # not have a current handler.
    do_gc_event_queues(to_remove, affected_users, affected_realms)

    logging.info(('Tornado removed %d idle event queues owned by %d users in %.3fs.'
                  + '  Now %d active queues, %s')
                 % (len(to_remove), len(affected_users), time.time() - start,
                    len(clients), handler_stats_string()))
    statsd.gauge('tornado.active_queues', len(clients))
    statsd.gauge('tornado.active_users', len(user_clients))

def dump_event_queues():
    # type: () -> None
    start = time.time()

    with open(settings.JSON_PERSISTENT_QUEUE_FILENAME, "w") as stored_queues:
        ujson.dump([(qid, client.to_dict()) for (qid, client) in six.iteritems(clients)],
                   stored_queues)

    logging.info('Tornado dumped %d event queues in %.3fs'
                 % (len(clients), time.time() - start))

def load_event_queues():
    # type: () -> None
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

    for client in six.itervalues(clients):
        # Put code for migrations due to event queue data format changes here

        add_to_client_dicts(client)

    logging.info('Tornado loaded %d event queues in %.3fs'
                 % (len(clients), time.time() - start))

def send_restart_events(immediate=False):
    # type: (bool) -> None
    event = dict(type='restart', server_generation=settings.SERVER_GENERATION) # type: Dict[str, Any]
    if immediate:
        event['immediate'] = True
    for client in six.itervalues(clients):
        if client.accepts_event(event):
            client.add_event(event.copy())

def setup_event_queue():
    # type: () -> None
    if not settings.TEST_SUITE:
        load_event_queues()
        atexit.register(dump_event_queues)
        # Make sure we dump event queues even if we exit via signal
        signal.signal(signal.SIGTERM, lambda signum, stack: sys.exit(1))
        tornado.autoreload.add_reload_hook(dump_event_queues) # type: ignore # TODO: Fix missing tornado.autoreload stub

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

def fetch_events(query):
    # type: (Mapping[str, Any]) -> Dict[str, Any]
    queue_id = query["queue_id"] # type: str
    dont_block = query["dont_block"] # type: bool
    last_event_id = query["last_event_id"] # type: int
    user_profile_id = query["user_profile_id"] # type: int
    new_queue_data = query.get("new_queue_data") # type: Optional[MutableMapping[str, Any]]
    user_profile_email = query["user_profile_email"] # type: text_type
    client_type_name = query["client_type_name"] # type: text_type
    handler_id = query["handler_id"] # type: int

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
                raise JsonableError(_("Bad event queue id: %s") % (queue_id,))
            if user_profile_id != client.user_profile_id:
                raise JsonableError(_("You are not authorized to get events from this queue"))
            client.event_queue.prune(last_event_id)
            was_connected = client.finish_current_handler()

        if not client.event_queue.empty() or dont_block:
            response = dict(events=client.event_queue.contents(),
                            handler_id=handler_id) # type: Dict[str, Any]
            if orig_queue_id is None:
                response['queue_id'] = queue_id
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
        if hasattr(e, 'to_json_error_msg') and callable(e.to_json_error_msg):
            return dict(type="error", handler_id=handler_id,
                        message=e.to_json_error_msg())
        raise e

    client.connect_handler(handler_id, client_type_name)
    return dict(type="async")

# The following functions are called from Django

# Workaround to support the Python-requests 1.0 transition of .json
# from a property to a function
requests_json_is_function = callable(requests.Response.json)
def extract_json_response(resp):
    # type: (requests.Response) -> Dict[str, Any]
    if requests_json_is_function:
        return resp.json()
    else:
        return resp.json # type: ignore # mypy trusts the stub, not the runtime type checking of this fn

def request_event_queue(user_profile, user_client, apply_markdown,
                        queue_lifespan_secs, event_types=None, all_public_streams=False,
                        narrow=[]):
    # type: (UserProfile, Client, bool, int, Optional[Iterable[str]], bool, Iterable[Sequence[text_type]]) -> Optional[str]
    if settings.TORNADO_SERVER:
        req = {'dont_block'    : 'true',
               'apply_markdown': ujson.dumps(apply_markdown),
               'all_public_streams': ujson.dumps(all_public_streams),
               'client'        : 'internal',
               'user_client'   : user_client.name,
               'narrow'        : ujson.dumps(narrow),
               'lifespan_secs' : queue_lifespan_secs}
        if event_types is not None:
            req['event_types'] = ujson.dumps(event_types)
        resp = requests.get(settings.TORNADO_SERVER + '/api/v1/events',
                            auth=requests.auth.HTTPBasicAuth(user_profile.email,
                                                             user_profile.api_key),
                            params=req)

        resp.raise_for_status()

        return extract_json_response(resp)['queue_id']

    return None

def get_user_events(user_profile, queue_id, last_event_id):
    # type: (UserProfile, str, int) -> List[Dict]
    if settings.TORNADO_SERVER:
        resp = requests.get(settings.TORNADO_SERVER + '/api/v1/events',
                            auth=requests.auth.HTTPBasicAuth(user_profile.email,
                                                             user_profile.api_key),
                            params={'queue_id'     : queue_id,
                                    'last_event_id': last_event_id,
                                    'dont_block'   : 'true',
                                    'client'       : 'internal'})

        resp.raise_for_status()

        return extract_json_response(resp)['events']


# Send email notifications to idle users
# after they are idle for 1 hour
NOTIFY_AFTER_IDLE_HOURS = 1
def build_offline_notification(user_profile_id, message_id):
    # type: (int, int) -> Dict[str, Any]
    return {"user_profile_id": user_profile_id,
            "message_id": message_id,
            "timestamp": time.time()}

def missedmessage_hook(user_profile_id, queue, last_for_client):
    # type: (int, ClientDescriptor, bool) -> None
    # Only process missedmessage hook when the last queue for a
    # client has been garbage collected
    if not last_for_client:
        return

    message_ids_to_notify = [] # type: List[Dict[str, Any]]
    for event in queue.event_queue.contents():
        if not event['type'] == 'message' or not event['flags']:
            continue

        if 'mentioned' in event['flags'] and 'read' not in event['flags']:
            notify_info = dict(message_id=event['message']['id'])

            if not event.get('push_notified', False):
                notify_info['send_push'] = True
            if not event.get('email_notified', False):
                notify_info['send_email'] = True
            message_ids_to_notify.append(notify_info)

    for notify_info in message_ids_to_notify:
        msg_id = notify_info['message_id']
        notice = build_offline_notification(user_profile_id, msg_id)
        if notify_info.get('send_push', False):
            queue_json_publish("missedmessage_mobile_notifications", notice, lambda notice: None)
        if notify_info.get('send_email', False):
            queue_json_publish("missedmessage_emails", notice, lambda notice: None)

def receiver_is_idle(user_profile_id, realm_presences):
    # type: (int, Optional[Dict[int, Dict[text_type, Dict[str, Any]]]]) -> bool
    # If a user has no message-receiving event queues, they've got no open zulip
    # session so we notify them
    all_client_descriptors = get_client_descriptors_for_user(user_profile_id)
    message_event_queues = [client for client in all_client_descriptors if client.accepts_messages()]
    off_zulip = len(message_event_queues) == 0

    # It's possible a recipient is not in the realm of a sender. We don't have
    # presence information in this case (and it's hard to get without an additional
    # db query) so we simply don't try to guess if this cross-realm recipient
    # has been idle for too long
    if realm_presences is None or user_profile_id not in realm_presences:
        return off_zulip

    # We want to find the newest "active" presence entity and compare that to the
    # activity expiry threshold.
    user_presence = realm_presences[user_profile_id]
    latest_active_timestamp = None
    idle = False

    for client, status in six.iteritems(user_presence):
        if (latest_active_timestamp is None or status['timestamp'] > latest_active_timestamp) and \
                status['status'] == 'active':
            latest_active_timestamp = status['timestamp']

    if latest_active_timestamp is None:
        idle = True
    else:
        active_datetime = timestamp_to_datetime(latest_active_timestamp)
        # 140 seconds is consistent with activity.js:OFFLINE_THRESHOLD_SECS
        idle = now() - active_datetime > datetime.timedelta(seconds=140)

    return off_zulip or idle

def process_message_event(event_template, users):
    # type: (Mapping[str, Any], Iterable[Mapping[str, Any]]) -> None
    realm_presences = {int(k): v for k, v in event_template['presences'].items()} # type: Dict[int, Dict[text_type, Dict[str, Any]]]
    sender_queue_id = event_template.get('sender_queue_id', None) # type: Optional[str]
    message_dict_markdown = event_template['message_dict_markdown'] # type: Dict[str, Any]
    message_dict_no_markdown = event_template['message_dict_no_markdown'] # type: Dict[str, Any]
    sender_id = message_dict_markdown['sender_id'] # type: int
    message_id = message_dict_markdown['id'] # type: int
    message_type = message_dict_markdown['type'] # type: str
    sending_client = message_dict_markdown['client'] # type: text_type

    # To remove duplicate clients: Maps queue ID to {'client': Client, 'flags': flags}
    send_to_clients = {} # type: Dict[str, Dict[str, Any]]

    # Extra user-specific data to include
    extra_user_data = {} # type: Dict[int, Any]

    if 'stream_name' in event_template and not event_template.get("invite_only"):
        for client in get_client_descriptors_for_realm_all_streams(event_template['realm_id']):
            send_to_clients[client.event_queue.id] = {'client': client, 'flags': None}
            if sender_queue_id is not None and client.event_queue.id == sender_queue_id:
                send_to_clients[client.event_queue.id]['is_sender'] = True

    for user_data in users:
        user_profile_id = user_data['id'] # type: int
        flags = user_data.get('flags', []) # type: Iterable[str]

        for client in get_client_descriptors_for_user(user_profile_id):
            send_to_clients[client.event_queue.id] = {'client': client, 'flags': flags}
            if sender_queue_id is not None and client.event_queue.id == sender_queue_id:
                send_to_clients[client.event_queue.id]['is_sender'] = True

        # If the recipient was offline and the message was a single or group PM to him
        # or she was @-notified potentially notify more immediately
        received_pm = message_type == "private" and user_profile_id != sender_id
        mentioned = 'mentioned' in flags
        idle = receiver_is_idle(user_profile_id, realm_presences)
        always_push_notify = user_data.get('always_push_notify', False)
        if (received_pm or mentioned) and (idle or always_push_notify):
            notice = build_offline_notification(user_profile_id, message_id)
            queue_json_publish("missedmessage_mobile_notifications", notice, lambda notice: None)
            notified = dict(push_notified=True) # type: Dict[str, bool]
            # Don't send missed message emails if always_push_notify is True
            if idle:
                # We require RabbitMQ to do this, as we can't call the email handler
                # from the Tornado process. So if there's no rabbitmq support do nothing
                queue_json_publish("missedmessage_emails", notice, lambda notice: None)
                notified['email_notified'] = True

            extra_user_data[user_profile_id] = notified

    for client_data in six.itervalues(send_to_clients):
        client = client_data['client']
        flags = client_data['flags']
        is_sender = client_data.get('is_sender', False) # type: bool
        extra_data = extra_user_data.get(client.user_profile_id, None) # type: Optional[Mapping[str, bool]]

        if not client.accepts_messages():
            # The actual check is the accepts_event() check below;
            # this line is just an optimization to avoid copying
            # message data unnecessarily
            continue

        if client.apply_markdown:
            message_dict = message_dict_markdown
        else:
            message_dict = message_dict_no_markdown

        # Make sure Zephyr mirroring bots know whether stream is invite-only
        if "mirror" in client.client_type_name and event_template.get("invite_only"):
            message_dict = message_dict.copy()
            message_dict["invite_only_stream"] = True

        user_event = dict(type='message', message=message_dict, flags=flags) # type: Dict[str, Any]
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

def process_event(event, users):
    # type: (Mapping[str, Any], Iterable[int]) -> None
    for user_profile_id in users:
        for client in get_client_descriptors_for_user(user_profile_id):
            if client.accepts_event(event):
                client.add_event(dict(event))

def process_userdata_event(event_template, users):
    # type: (Mapping[str, Any], Iterable[Mapping[str, Any]]) -> None
    for user_data in users:
        user_profile_id = user_data['id']
        user_event = dict(event_template) # shallow copy, but deep enough for our needs
        for key in user_data.keys():
            if key != "id":
                user_event[key] = user_data[key]

        for client in get_client_descriptors_for_user(user_profile_id):
            if client.accepts_event(user_event):
                client.add_event(user_event)

def process_notification(notice):
    # type: (Mapping[str, Any]) -> None
    event = notice['event'] # type: Mapping[str, Any]
    users = notice['users'] # type: Union[Iterable[int], Iterable[Mapping[str, Any]]]
    if event['type'] in ["update_message"]:
        process_userdata_event(event, cast(Iterable[Mapping[str, Any]], users))
    elif event['type'] == "message":
        process_message_event(event, cast(Iterable[Mapping[str, Any]], users))
    else:
        process_event(event, cast(Iterable[int], users))

# Runs in the Django process to send a notification to Tornado.
#
# We use JSON rather than bare form parameters, so that we can represent
# different types and for compatibility with non-HTTP transports.

def send_notification_http(data):
    # type: (Mapping[str, Any]) -> None
    if settings.TORNADO_SERVER and not settings.RUNNING_INSIDE_TORNADO:
        requests.post(settings.TORNADO_SERVER + '/notify_tornado', data=dict(
                data   = ujson.dumps(data),
                secret = settings.SHARED_SECRET))
    else:
        process_notification(data)

def send_notification(data):
    # type: (Mapping[str, Any]) -> None
    queue_json_publish("notify_tornado", data, send_notification_http)

def send_event(event, users):
    # type: (Mapping[str, Any], Union[Iterable[int], Iterable[Mapping[str, Any]]]) -> None
    """`users` is a list of user IDs, or in the case of `message` type
    events, a list of dicts describing the users and metadata about
    the user/message pair."""
    queue_json_publish("notify_tornado",
                       dict(event=event, users=users),
                       send_notification_http)

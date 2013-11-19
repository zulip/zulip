from __future__ import absolute_import

from django.conf import settings
from collections import deque
import os
import time
import socket
import logging
import ujson
import requests
import cPickle as pickle
import atexit
import sys
import signal
import tornado
import random
import traceback
from zerver.lib.utils import statsd
from zerver.middleware import async_request_restart
from zerver.models import get_client

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
    def __init__(self, user_profile_id, realm_id, event_queue, event_types, client_type,
                 apply_markdown=True, all_public_streams=False, lifespan_secs=0):
        # These objects are serialized on shutdown and restored on restart.
        # If fields are added or semantics are changed, temporary code must be
        # added to load_event_queues() to update the restored objects.
        # Additionally, the to_dict and from_dict methods must be updated
        self.user_profile_id = user_profile_id
        self.realm_id = realm_id
        self.current_handler = None
        self.event_queue = event_queue
        self.queue_timeout = lifespan_secs
        self.event_types = event_types
        self.last_connection_time = time.time()
        self.apply_markdown = apply_markdown
        self.all_public_streams = all_public_streams
        self.client_type = client_type
        self._timeout_handle = None

        # Clamp queue_timeout to between minimum and maximum timeouts
        self.queue_timeout = max(IDLE_EVENT_QUEUE_TIMEOUT_SECS, min(self.queue_timeout, MAX_QUEUE_TIMEOUT_SECS))

    def to_dict(self):
        return dict(user_profile_id=self.user_profile_id,
                    realm_id=self.realm_id,
                    event_queue=self.event_queue.to_dict(),
                    queue_timeout=self.queue_timeout,
                    event_types=self.event_types,
                    last_connection_time=self.last_connection_time,
                    apply_markdown=self.apply_markdown,
                    all_public_streams=self.all_public_streams,
                    client_type=self.client_type.name)

    @classmethod
    def from_dict(cls, d):
        ret = cls(d['user_profile_id'], d['realm_id'],
                  EventQueue.from_dict(d['event_queue']), d['event_types'],
                  get_client(d['client_type']), d['apply_markdown'], d['all_public_streams'],
                  d['queue_timeout'])
        ret.last_connection_time = d['last_connection_time']
        return ret

    def prepare_for_pickling(self):
        self.current_handler = None
        self._timeout_handle = None

    def add_event(self, event):
        if self.current_handler is not None:
            async_request_restart(self.current_handler._request)

        self.event_queue.push(event)
        logging.info("DEBUG: Added %s event to queue %s: handler is %s" % (
                event.get("type"),
                self.event_queue.id,
                self.current_handler is not None))
        if self.current_handler is not None:
            try:
                self.current_handler._request._log_data['extra'] = "[%s/1]" % (self.event_queue.id,)
                self.current_handler.zulip_finish(dict(result='success', msg='',
                                                       events=[event],
                                                       queue_id=self.event_queue.id),
                                                  self.current_handler._request,
                                                  apply_markdown=self.apply_markdown)
                logging.info("DEBUG: Successfully called back on queue %s" % (self.event_queue.id))
            except socket.error:
                logging.info("DEBUG: Got error adding event to queue %s" % (self.event_queue.id))
                traceback.print_exc()
            self.disconnect_handler()

    def accepts_event_type(self, type):
        if self.event_types is None:
            return True
        return type in self.event_types

    def idle(self, now):
        if not hasattr(self, 'queue_timeout'):
            self.queue_timeout = IDLE_EVENT_QUEUE_TIMEOUT_SECS

        return (self.current_handler is None
                and now - self.last_connection_time >= self.queue_timeout)

    def connect_handler(self, handler):
        self.current_handler = handler
        self.last_connection_time = time.time()

        if self.accepts_event_type('heartbeat'):
            def timeout_callback():
                self._timeout_handle = None
                # We already checked whether the client accepts heartbeats
                self.add_event(dict(type='heartbeat'))
            ioloop = tornado.ioloop.IOLoop.instance()
            heartbeat_time = time.time() + HEARTBEAT_MIN_FREQ_SECS + random.randint(0, 10)
            self._timeout_handle = ioloop.add_timeout(heartbeat_time, timeout_callback)

        logging.info("DEBUG: connected handler for queue %s" % (self.event_queue.id,))

    def disconnect_handler(self):
        if self.current_handler is not None:
            logging.info("DEBUG: disconnected handler for queue %s" % (self.event_queue.id,))
        self.current_handler = None
        if self._timeout_handle is not None:
            ioloop = tornado.ioloop.IOLoop.instance()
            ioloop.remove_timeout(self._timeout_handle)
            self._timeout_handle = None

    def cleanup(self):
        do_gc_event_queues([self.event_queue.id], [self.user_profile_id],
                           [self.realm_id])

class EventQueue(object):
    def __init__(self, id):
        self.queue = deque()
        self.next_event_id = 0
        self.id = id

    def to_dict(self):
        return dict(id=self.id, next_event_id=self.next_event_id,
                    queue=list(self.queue))

    @classmethod
    def from_dict(cls, d):
        ret = cls(d['id'])
        ret.next_event_id = d['next_event_id']
        ret.queue = deque(d['queue'])
        return ret

    def push(self, event):
        event['id'] = self.next_event_id
        self.next_event_id += 1
        self.queue.append(event)

    def pop(self):
        return self.queue.popleft()

    def empty(self):
        return len(self.queue) == 0

    def prune(self, through_id):
        while not self.empty() and self.queue[0]['id'] <= through_id:
            self.pop()

    def contents(self):
        return list(self.queue)

# maps queue ids to client descriptors
clients = {}
# maps user id to list of client descriptors
user_clients = {}
# maps realm id to list of client descriptors with all_public_streams=True
realm_clients_all_streams = {}

# list of registered gc hooks.
# each one will be called with a user profile id, queue, and bool
# last_for_client that is true if this is the last queue pertaining
# to this user_profile_id
# that is about to be deleted
gc_hooks = []

next_queue_id = 0

def add_client_gc_hook(hook):
    gc_hooks.append(hook)

def get_client_descriptor(queue_id):
    return clients.get(queue_id)

def get_client_descriptors_for_user(user_profile_id):
    return user_clients.get(user_profile_id, [])

def get_client_descriptors_for_realm_all_streams(realm_id):
    return realm_clients_all_streams.get(realm_id, [])

def allocate_client_descriptor(user_profile_id, realm_id, event_types, client_type,
                               apply_markdown, all_public_streams, lifespan_secs):
    global next_queue_id
    id = str(settings.SERVER_GENERATION) + ':' + str(next_queue_id)
    next_queue_id += 1
    client = ClientDescriptor(user_profile_id, realm_id, EventQueue(id), event_types, client_type,
                              apply_markdown, all_public_streams, lifespan_secs)
    clients[id] = client
    user_clients.setdefault(user_profile_id, []).append(client)
    if all_public_streams:
        realm_clients_all_streams.setdefault(realm_id, []).append(client)
    return client

def do_gc_event_queues(to_remove, affected_users, affected_realms):
    def filter_client_dict(client_dict, key):
        if key not in client_dict:
            return

        new_client_list = filter(lambda c: c.event_queue.id not in to_remove,
                                client_dict[key])
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
    start = time.time()
    to_remove = set()
    affected_users = set()
    affected_realms = set()
    for (id, client) in clients.iteritems():
        if client.idle(start):
            to_remove.add(id)
            affected_users.add(client.user_profile_id)
            affected_realms.add(client.realm_id)

    do_gc_event_queues(to_remove, affected_users, affected_realms)

    logging.info(('Tornado removed %d idle event queues owned by %d users in %.3fs.'
                  + '  Now %d active queues')
                 % (len(to_remove), len(affected_users), time.time() - start,
                    len(clients)))
    statsd.gauge('tornado.active_queues', len(clients))
    statsd.gauge('tornado.active_users', len(user_clients))

def dump_event_queues():
    start = time.time()

    with file(settings.JSON_PERSISTENT_QUEUE_FILENAME, "w") as stored_queues:
        ujson.dump([(qid, client.to_dict()) for (qid, client) in clients.iteritems()],
                   stored_queues)

    logging.info('Tornado dumped %d event queues in %.3fs'
                 % (len(clients), time.time() - start))

def load_event_queues():
    global clients
    start = time.time()

    if os.path.exists(settings.PERSISTENT_QUEUE_FILENAME):
        try:
            with file(settings.PERSISTENT_QUEUE_FILENAME, "r") as stored_queues:
                clients = pickle.load(stored_queues)
        except (IOError, EOFError):
            pass
    else:
        # ujson chokes on bad input pretty easily.  We separate out the actual
        # file reading from the loading so that we don't silently fail if we get
        # bad input.
        try:
            with file(settings.JSON_PERSISTENT_QUEUE_FILENAME, "r") as stored_queues:
                json_data = stored_queues.read()
            try:
                clients = dict((qid, ClientDescriptor.from_dict(client))
                               for (qid, client) in ujson.loads(json_data))
            except Exception:
                logging.exception("Could not deserialize event queues")
        except (IOError, EOFError):
            pass

    for client in clients.itervalues():
        # Put code for migrations due to event queue data format changes here

        user_clients.setdefault(client.user_profile_id, []).append(client)
        if client.all_public_streams:
            realm_clients_all_streams.setdefault(client.realm_id, []).append(client)

    logging.info('Tornado loaded %d event queues in %.3fs'
                 % (len(clients), time.time() - start))

def send_restart_events():
    event = dict(type='restart', server_generation=settings.SERVER_GENERATION)
    for client in clients.itervalues():
        if not client.accepts_event_type('restart'):
            continue
        client.add_event(event.copy())

def setup_event_queue():
    load_event_queues()
    atexit.register(dump_event_queues)
    # Make sure we dump event queues even if we exit via signal
    signal.signal(signal.SIGTERM, lambda signum, stack: sys.exit(1))

    try:
        os.rename(settings.PERSISTENT_QUEUE_FILENAME, "/var/tmp/event_queues.pickle.last")
    except OSError:
        pass

    try:
        os.rename(settings.JSON_PERSISTENT_QUEUE_FILENAME, "/var/tmp/event_queues.json.last")
    except OSError:
        pass

    # Set up event queue garbage collection
    ioloop = tornado.ioloop.IOLoop.instance()
    pc = tornado.ioloop.PeriodicCallback(gc_event_queues,
                                         EVENT_QUEUE_GC_FREQ_MSECS, ioloop)
    pc.start()

    send_restart_events()

# The following functions are called from Django

# Workaround to support the Python-requests 1.0 transition of .json
# from a property to a function
requests_json_is_function = callable(requests.Response.json)
def extract_json_response(resp):
    if requests_json_is_function:
        return resp.json()
    else:
        return resp.json

def request_event_queue(user_profile, user_client, apply_markdown,
                        queue_lifespan_secs, event_types=None, all_public_streams=False):
    if settings.TORNADO_SERVER:
        req = {'dont_block'    : 'true',
               'apply_markdown': ujson.dumps(apply_markdown),
               'all_public_streams': ujson.dumps(all_public_streams),
               'client'        : 'internal',
               'user_client'   : user_client.name,
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

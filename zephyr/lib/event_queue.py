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
from zephyr.lib.utils import statsd
from zephyr.middleware import async_request_restart
from zephyr.models import get_client

# The idle timeout used to be a week, but we found that in that
# situation, queues from dead browser sessions would grow quite large
# due to the accumulation of message data in those queues.
IDLE_EVENT_QUEUE_TIMEOUT_SECS = 60 * 10
EVENT_QUEUE_GC_FREQ_MSECS = 1000 * 60 * 5
# The heartbeats effectively act as a server-side timeout for
# get_events().  The actual timeout value is randomized for each
# client connection based on the below value.  We ensure that the
# maximum timeout value is 55 seconds, to deal with crappy home
# wireless routers that kill "inactive" http connections.
HEARTBEAT_MIN_FREQ_SECS = 45

class ClientDescriptor(object):
    def __init__(self, user_profile_id, id, event_types, client_type,
                 apply_markdown=True):
        self.user_profile_id = user_profile_id
        self.current_handler = None
        self.event_queue = EventQueue(id)
        self.event_types = event_types
        self.last_connection_time = time.time()
        self.apply_markdown = apply_markdown
        self.client_type = client_type
        self._timeout_handle = None

    def prepare_for_pickling(self):
        self.current_handler = None
        self._timeout_handle = None

    def add_event(self, event):
        if self.current_handler is not None:
            async_request_restart(self.current_handler._request)

        self.event_queue.push(event)
        if self.current_handler is not None:
            try:
                self.current_handler.humbug_finish(dict(result='success', msg='',
                                                        events=[event],
                                                        queue_id=self.event_queue.id),
                                                   self.current_handler._request,
                                                   apply_markdown=self.apply_markdown)
            except socket.error:
                pass
            self.disconnect_handler()

    def accepts_event_type(self, type):
        if self.event_types is None:
            return True
        return type in self.event_types

    def idle(self, now):
        return (self.current_handler is None
                and now - self.last_connection_time >= IDLE_EVENT_QUEUE_TIMEOUT_SECS)

    def connect_handler(self, handler):
        self.current_handler = handler
        self.last_connection_time = time.time()
        def timeout_callback():
            self._timeout_handle = None
            # All clients get heartbeat events
            self.add_event(dict(type='heartbeat'))
        ioloop = tornado.ioloop.IOLoop.instance()
        heartbeat_time = time.time() + HEARTBEAT_MIN_FREQ_SECS + random.randint(0, 10)
        self._timeout_handle = ioloop.add_timeout(heartbeat_time, timeout_callback)

    def disconnect_handler(self):
        self.current_handler = None
        if self._timeout_handle is not None:
            ioloop = tornado.ioloop.IOLoop.instance()
            ioloop.remove_timeout(self._timeout_handle)
            self._timeout_handle = None

class EventQueue(object):
    def __init__(self, id):
        self.queue = deque()
        self.next_event_id = 0
        self.id = id

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

def allocate_client_descriptor(user_profile_id, event_types, client_type,
                               apply_markdown):
    global next_queue_id
    id = str(settings.SERVER_GENERATION) + ':' + str(next_queue_id)
    next_queue_id += 1
    client = ClientDescriptor(user_profile_id, id, event_types, client_type,
                              apply_markdown)
    clients[id] = client
    user_clients.setdefault(user_profile_id, []).append(client)
    return client

def gc_event_queues():
    start = time.time()
    to_remove = set()
    affected_users = set()
    for (id, client) in clients.iteritems():
        if client.idle(start):
            to_remove.add(id)
            affected_users.add(client.user_profile_id)

    for user_id in affected_users:
        new_client_list = filter(lambda c: c.event_queue.id not in to_remove,
                                user_clients[user_id])
        if len(new_client_list) == 0:
            del user_clients[user_id]
        else:
            user_clients[user_id] = new_client_list

    for id in to_remove:
        for cb in gc_hooks:
            cb(clients[id].user_profile_id, clients[id], clients[id].user_profile_id not in user_clients)
        del clients[id]

    logging.info(('Tornado removed %d idle event queues owned by %d users in %.3fs.'
                  + '  Now %d active queues')
                 % (len(to_remove), len(affected_users), time.time() - start,
                    len(clients)))
    statsd.gauge('tornado.active_queues', len(clients))
    statsd.gauge('tornado.active_users', len(user_clients))

def dump_event_queues():
    start = time.time()
    # Remove unpickle-able attributes
    for client in clients.itervalues():
        client.prepare_for_pickling()

    with file(settings.PERSISTENT_QUEUE_FILENAME, "w") as stored_queues:
        pickle.dump(clients, stored_queues)

    logging.info('Tornado dumped %d event queues in %.3fs'
                 % (len(clients), time.time() - start))

def load_event_queues():
    global clients
    start = time.time()
    try:
        with file(settings.PERSISTENT_QUEUE_FILENAME, "r") as stored_queues:
            clients = pickle.load(stored_queues)
    except (IOError, EOFError):
        pass

    for client in clients.itervalues():
        # The following client_type block can be dropped once we've
        # cleared out all our old event queues
        if not hasattr(client, 'client_type'):
            client.client_type = get_client("website")
        user_clients.setdefault(client.user_profile_id, []).append(client)

    logging.info('Tornado loaded %d event queues in %.3fs'
                 % (len(clients), time.time() - start))

def send_restart_events():
    event = dict(type='restart', server_generation=settings.SERVER_GENERATION)
    for client in clients.itervalues():
        # All clients get restart events
        client.add_event(event.copy())

def setup_event_queue():
    load_event_queues()
    atexit.register(dump_event_queues)
    # Make sure we dump event queues even if we exit via signal
    signal.signal(signal.SIGTERM, lambda signum, stack: sys.exit(1))

    try:
        os.remove(settings.PERSISTENT_QUEUE_FILENAME)
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
                        event_types=None):
    if settings.TORNADO_SERVER:
        req = {'dont_block'    : 'true',
               'apply_markdown': ujson.dumps(apply_markdown),
               'client'        : 'internal',
               'user_client'   : user_client.name}
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

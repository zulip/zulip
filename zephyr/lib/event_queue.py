from django.conf import settings
from collections import deque
from tornado.ioloop import PeriodicCallback
import time
import socket
import logging
import simplejson

IDLE_EVENT_QUEUE_TIMEOUT_SECS = 60 * 10

class ClientDescriptor(object):
    def __init__(self, user_profile_id, id, apply_markdown=True):
        self.user_profile_id = user_profile_id
        self.current_handler = None
        self.event_queue = EventQueue(id)
        self.last_connection_time = time.time()
        self.apply_markdown = apply_markdown

    def add_event(self, event):
        if self.current_handler is not None:
            self.current_handler._request._time_restarted = time.time()

        self.event_queue.push(event)
        self.check_connection()
        if self.current_handler is not None:
            try:
                self.current_handler.humbug_finish(dict(result='success', msg='',
                                                        events=[event],
                                                        queue_id=self.event_queue.id),
                                                   self.current_handler._request,
                                                   apply_markdown=self.apply_markdown)
                return
            except socket.error:
                pass

    def idle(self, now):
        self.check_connection()
        return (self.current_handler is None
                and now - self.last_connection_time >= IDLE_EVENT_QUEUE_TIMEOUT_SECS)

    def connect_handler(self, handler):
        self.current_handler = handler
        self.last_connection_time = time.time()

    def disconnect_handler(self):
        self.current_handler = None

    def check_connection(self):
        if (self.current_handler is not None
            and self.current_handler.request.connection.stream.closed()):
            self.current_handler = None

class EventQueue(object):
    def __init__(self, id):
        self.queue = deque()
        self.connected_handler = None
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

next_queue_id = 0

def allocate_client_descriptor(user_profile_id, apply_markdown):
    global next_queue_id
    id = str(settings.SERVER_GENERATION) + ':' + str(next_queue_id)
    next_queue_id += 1
    client = ClientDescriptor(user_profile_id, id, apply_markdown)
    clients[id] = client
    user_clients.setdefault(user_profile_id, []).append(client)
    return client

EVENT_QUEUE_GC_FREQ_MSECS = 1000 * 60 * 5

def gc_event_queues():
    start = time.time()
    to_remove = set()
    affected_users = set()
    for (id, client) in clients.iteritems():
        if client.idle(start):
            to_remove.add(id)
            affected_users.add(client.user_profile_id)

    for id in to_remove:
        del clients[id]

    for user_id in affected_users:
        new_client_list = filter(lambda c: c.event_queue.id not in to_remove,
                                user_clients[user_id])
        user_clients[user_id] = new_client_list

    logging.info(('Tornado removed %d idle event queues owned by %d users in %.3fs.'
                  + '  Now %d active queues')
                 % (len(to_remove), len(affected_users), time.time() - start,
                    len(clients)))

def setup_event_queue_gc(io_loop):
    pc = PeriodicCallback(gc_event_queues, EVENT_QUEUE_GC_FREQ_MSECS, io_loop)
    pc.start()

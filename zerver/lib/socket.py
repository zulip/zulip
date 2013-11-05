from __future__ import absolute_import

from django.conf import settings
from django.utils.importlib import import_module
from django.utils import timezone
from django.contrib.sessions.models import Session as djSession

import sockjs.tornado
import tornado.ioloop
import ujson
import logging
import time
import redis

from zerver.models import UserProfile, get_user_profile_by_id, get_client
from zerver.lib.queue import queue_json_publish
from zerver.lib.actions import check_send_message, extract_recipients
from zerver.decorator import JsonableError
from zerver.lib.utils import statsd
from zerver.lib.event_queue import get_client_descriptor

djsession_engine = import_module(settings.SESSION_ENGINE)
def get_user_profile(session_id):
    if session_id is None:
        return None

    try:
        djsession = djSession.objects.get(expire_date__gt=timezone.now(),
                                          session_key=session_id)
    except djSession.DoesNotExist:
        return None

    session_store = djsession_engine.SessionStore(djsession.session_key)

    try:
        return UserProfile.objects.get(pk=session_store['_auth_user_id'])
    except UserProfile.DoesNotExist:
        return None

connections = dict()

def get_connection(id):
    return connections.get(id)

def register_connection(id, conn):
    conn.client_id = id
    connections[conn.client_id] = conn

def deregister_connection(conn):
    del connections[conn.client_id]

def fake_log_line(conn_info, time, ret_code, path, email):
    # These two functions are copied from our middleware.  At some
    # point we will just run the middleware directly.
    def timedelta_ms(timedelta):
        return timedelta * 1000

    def format_timedelta(timedelta):
        if (timedelta >= 1):
            return "%.1fs" % (timedelta)
        return "%.0fms" % (timedelta_ms(timedelta),)

    logging.info('%-15s %-7s %3d %5s %s (%s)' %
                 (conn_info.ip, 'SOCKET', ret_code, format_timedelta(time),
                  path, email))

redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)

def req_redis_key(client_id, req_id):
    return 'socket_req_status:%s:%s' % (client_id, req_id)

class SocketAuthError(Exception):
    def __init__(self, msg):
        self.msg = msg

class SocketConnection(sockjs.tornado.SockJSConnection):
    def on_open(self, info):
        self.authenticated = False
        self.session.user_profile = None
        self.browser_session_id = info.get_cookie(settings.SESSION_COOKIE_NAME).value
        self.csrf_token = info.get_cookie(settings.CSRF_COOKIE_NAME).value

        ioloop = tornado.ioloop.IOLoop.instance()
        self.timeout_handle = ioloop.add_timeout(time.time() + 10, self.close)

        fake_log_line(info, 0, 200, 'Connection opened using %s' % (self.session.transport_name,), 'unknown')

    def authenticate_client(self, msg):
        if self.authenticated:
            self.session.send_message({'req_id': msg['req_id'],
                                       'response': {'result': 'error', 'msg': 'Already authenticated'}})
            return

        user_profile = get_user_profile(self.browser_session_id)
        if user_profile is None:
            raise SocketAuthError('Unknown or missing session')
        self.session.user_profile = user_profile

        if msg['request']['csrf_token'] != self.csrf_token:
            raise SocketAuthError('CSRF token does not match that in cookie')

        if not 'queue_id' in msg['request']:
            raise SocketAuthError("Missing 'queue_id' argument")

        queue_id = msg['request']['queue_id']
        client = get_client_descriptor(queue_id)
        if client is None:
            raise SocketAuthError('Bad event queue id: %s' % (queue_id,))

        if user_profile.id != client.user_profile_id:
            raise SocketAuthError("You are not the owner of the queue with id '%s'" % (queue_id,))

        register_connection(queue_id, self)

        self.session.send_message({'req_id': msg['req_id'],
                                   'response': {'result': 'success', 'msg': ''}})
        self.authenticated = True
        fake_log_line(self.session.conn_info, 0, 200, "Authenticated using %s" % (self.session.transport_name,),
                      user_profile.email)
        ioloop = tornado.ioloop.IOLoop.instance()
        ioloop.remove_timeout(self.timeout_handle)

    def on_message(self, msg):
        start_time = time.time()
        msg = ujson.loads(msg)

        if msg['type'] == 'auth':
            try:
                self.authenticate_client(msg)
            except SocketAuthError as e:
                fake_log_line(self.session.conn_info, 0, 403, e.msg, 'unknown')
                self.session.send_message({'req_id': msg['req_id'],
                                           'response': {'result': 'error', 'msg': e.msg}})
            return
        else:
            if not self.authenticated:
                error_msg = 'Not yet authenticated'
                fake_log_line(self.session.conn_info, 0, 403, error_msg, 'unknown')
                self.session.send_message({'req_id': msg['req_id'],
                                           'response': {'result': 'error', 'msg': error_msg}})
                return

        req = msg['request']
        req['sender_id'] = self.session.user_profile.id
        req['client_name'] = req['client']

        redis_key = req_redis_key(self.client_id, msg['req_id'])
        with redis_client.pipeline() as pipeline:
            pipeline.hmset(redis_key, {'status': 'receieved'});
            pipeline.expire(redis_key, 60 * 5)
            pipeline.execute()

        queue_json_publish("message_sender", dict(request=req,
                                                  req_id=msg['req_id'],
                                                  server_meta=dict(client_id=self.client_id,
                                                                   return_queue="tornado_return",
                                                                   start_time=start_time)),
                           fake_message_sender)

    def on_close(self):
        deregister_connection(self)
        if self.session.user_profile is None:
            fake_log_line(self.session.conn_info, 0, 408,
                          'Timeout while waiting for authentication', 'unknown')
        else:
            fake_log_line(self.session.conn_info, 0, 200,
                          'Connection closed', 'unknown')

def fake_message_sender(event):
    req = event['request']
    try:
        sender = get_user_profile_by_id(req['sender_id'])
        client = get_client(req['client_name'])

        msg_id = check_send_message(sender, client, req['type'],
                                    extract_recipients(req['to']),
                                    req['subject'], req['content'])
        resp = {"result": "success", "msg": "", "id": msg_id}
    except JsonableError as e:
        resp = {"result": "error", "msg": str(e)}

    result = {'response': resp, 'req_id': event['req_id'],
              'server_meta': event['server_meta']}
    respond_send_message(result)

def respond_send_message(data):
    connection = get_connection(data['server_meta']['client_id'])
    if connection is not None:
        connection.session.send_message({'req_id': data['req_id'], 'response': data['response']})

        time_elapsed = time.time() - data['server_meta']['start_time']
        fake_log_line(connection.session.conn_info,
                      time_elapsed,
                      200, 'send_message', connection.session.user_profile.email)
        # Fake the old JSON send_message endpoint
        statsd_prefix = "webreq.json.send_message.total"
        statsd.timing(statsd_prefix, time_elapsed * 1000)

sockjs_router = sockjs.tornado.SockJSRouter(SocketConnection, "/sockjs",
                                            {'sockjs_url': 'https://%s/static/third/sockjs/sockjs-0.3.4.js' % (settings.EXTERNAL_HOST,),
                                             'disabled_transports': ['eventsource', 'htmlfile']})
def get_sockjs_router():
    return sockjs_router

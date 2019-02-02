# See https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html#websockets
# for high-level documentation on this subsystem.

from typing import Any, Dict, Mapping, Optional, Union

from django.conf import settings
from django.utils.timezone import now as timezone_now
from django.utils.translation import ugettext as _
from django.contrib.sessions.models import Session as djSession
try:
    from django.middleware.csrf import _compare_salted_tokens
except ImportError:
    # This function was added in Django 1.10.
    def _compare_salted_tokens(token1: str, token2: str) -> bool:
        return token1 == token2

import sockjs.tornado
from sockjs.tornado.session import ConnectionInfo
import tornado.ioloop
import ujson
import logging

from zerver.models import UserProfile, get_user_profile_by_id
from zerver.lib.queue import queue_json_publish
from zerver.decorator import JsonableError
from zerver.middleware import record_request_start_data, record_request_stop_data, \
    record_request_restart_data, write_log_line, format_timedelta
from zerver.lib.redis_utils import get_redis_client
from zerver.lib.sessions import get_session_user
from zerver.tornado.event_queue import get_client_descriptor
from zerver.tornado.exceptions import BadEventQueueIdError
from zerver.tornado.sharding import tornado_return_queue_name

logger = logging.getLogger('zulip.socket')

def get_user_profile(session_id: Optional[str]) -> Optional[UserProfile]:
    if session_id is None:
        return None

    try:
        djsession = djSession.objects.get(expire_date__gt=timezone_now(),
                                          session_key=session_id)
    except djSession.DoesNotExist:
        return None

    try:
        return get_user_profile_by_id(get_session_user(djsession))
    except (UserProfile.DoesNotExist, KeyError):
        return None

connections = dict()  # type: Dict[Union[int, str], 'SocketConnection']

def get_connection(id: Union[int, str]) -> Optional['SocketConnection']:
    return connections.get(id)

def register_connection(id: Union[int, str], conn: 'SocketConnection') -> None:
    # Kill any old connections if they exist
    if id in connections:
        connections[id].close()

    conn.client_id = id
    connections[conn.client_id] = conn

def deregister_connection(conn: 'SocketConnection') -> None:
    assert conn.client_id is not None
    del connections[conn.client_id]

redis_client = get_redis_client()

def req_redis_key(req_id: str) -> str:
    return 'socket_req_status:%s' % (req_id,)

class CloseErrorInfo:
    def __init__(self, status_code: int, err_msg: str) -> None:
        self.status_code = status_code
        self.err_msg = err_msg

class SocketConnection(sockjs.tornado.SockJSConnection):
    client_id = None  # type: Optional[Union[int, str]]

    def on_open(self, info: ConnectionInfo) -> None:
        log_data = dict(extra='[transport=%s]' % (self.session.transport_name,))
        record_request_start_data(log_data)

        ioloop = tornado.ioloop.IOLoop.instance()

        self.authenticated = False
        self.session.user_profile = None
        self.close_info = None  # type: Optional[CloseErrorInfo]
        self.did_close = False

        try:
            self.browser_session_id = info.get_cookie(settings.SESSION_COOKIE_NAME).value
            self.csrf_token = info.get_cookie(settings.CSRF_COOKIE_NAME).value
        except AttributeError:
            # The request didn't contain the necessary cookie values.  We can't
            # close immediately because sockjs-tornado doesn't expect a close
            # inside on_open(), so do it on the next tick.
            self.close_info = CloseErrorInfo(403, "Initial cookie lacked required values")
            ioloop.add_callback(self.close)
            return

        def auth_timeout() -> None:
            self.close_info = CloseErrorInfo(408, "Timeout while waiting for authentication")
            self.close()

        self.timeout_handle = ioloop.call_later(10, auth_timeout)
        write_log_line(log_data, path='/socket/open', method='SOCKET',
                       remote_ip=info.ip, email='unknown', client_name='?')

    def authenticate_client(self, msg: Dict[str, Any]) -> None:
        if self.authenticated:
            self.session.send_message({'req_id': msg['req_id'], 'type': 'response',
                                       'response': {'result': 'error',
                                                    'msg': 'Already authenticated'}})
            return

        user_profile = get_user_profile(self.browser_session_id)
        if user_profile is None:
            raise JsonableError(_('Unknown or missing session'))
        self.session.user_profile = user_profile

        if 'csrf_token' not in msg['request']:
            # Debugging code to help with understanding #6961
            logging.error("CSRF token missing from websockets auth request: %s" % (msg['request'],))
            raise JsonableError(_('CSRF token entry missing from request'))
        if not _compare_salted_tokens(msg['request']['csrf_token'], self.csrf_token):
            raise JsonableError(_('CSRF token does not match that in cookie'))

        if 'queue_id' not in msg['request']:
            raise JsonableError(_("Missing 'queue_id' argument"))

        queue_id = msg['request']['queue_id']
        client = get_client_descriptor(queue_id)
        if client is None:
            raise BadEventQueueIdError(queue_id)

        if user_profile.id != client.user_profile_id:
            raise JsonableError(_("You are not the owner of the queue with id '%s'") % (queue_id,))

        self.authenticated = True
        register_connection(queue_id, self)

        response = {'req_id': msg['req_id'], 'type': 'response',
                    'response': {'result': 'success', 'msg': ''}}

        status_inquiries = msg['request'].get('status_inquiries')
        if status_inquiries is not None:
            results = {}  # type: Dict[str, Dict[str, str]]
            for inquiry in status_inquiries:
                status = redis_client.hgetall(req_redis_key(inquiry))  # type: Dict[bytes, bytes]
                if len(status) == 0:
                    result = {'status': 'not_received'}
                elif b'response' not in status:
                    result = {'status': status[b'status'].decode('utf-8')}
                else:
                    result = {'status': status[b'status'].decode('utf-8'),
                              'response': ujson.loads(status[b'response'])}
                results[str(inquiry)] = result
            response['response']['status_inquiries'] = results

        self.session.send_message(response)
        ioloop = tornado.ioloop.IOLoop.instance()
        ioloop.remove_timeout(self.timeout_handle)

    def on_message(self, msg_raw: str) -> None:
        log_data = dict(extra='[transport=%s' % (self.session.transport_name,))
        record_request_start_data(log_data)
        msg = ujson.loads(msg_raw)

        if self.did_close:
            user_email = 'unknown'
            if self.session.user_profile is not None:
                user_email = self.session.user_profile.email
            logger.info("Received message on already closed socket! transport=%s user=%s client_id=%s"
                        % (self.session.transport_name,
                           user_email,
                           self.client_id))

        self.session.send_message({'req_id': msg['req_id'], 'type': 'ack'})

        if msg['type'] == 'auth':
            log_data['extra'] += ']'
            try:
                self.authenticate_client(msg)
                # TODO: Fill in the correct client
                write_log_line(log_data, path='/socket/auth', method='SOCKET',
                               remote_ip=self.session.conn_info.ip,
                               email=self.session.user_profile.email,
                               client_name='?')
            except JsonableError as e:
                response = e.to_json()
                self.session.send_message({'req_id': msg['req_id'], 'type': 'response',
                                           'response': response})
                write_log_line(log_data, path='/socket/auth', method='SOCKET',
                               remote_ip=self.session.conn_info.ip,
                               email='unknown', client_name='?',
                               status_code=403, error_content=ujson.dumps(response))
            return
        else:
            if not self.authenticated:
                response = {'result': 'error', 'msg': "Not yet authenticated"}
                self.session.send_message({'req_id': msg['req_id'], 'type': 'response',
                                           'response': response})
                write_log_line(log_data, path='/socket/service_request', method='SOCKET',
                               remote_ip=self.session.conn_info.ip,
                               email='unknown', client_name='?',
                               status_code=403, error_content=ujson.dumps(response))
                return

        redis_key = req_redis_key(msg['req_id'])
        with redis_client.pipeline() as pipeline:
            pipeline.hmset(redis_key, {'status': 'received'})
            pipeline.expire(redis_key, 60 * 60 * 24)
            pipeline.execute()

        record_request_stop_data(log_data)
        request_environ = dict(REMOTE_ADDR=self.session.conn_info.ip)
        queue_json_publish("message_sender",
                           dict(request=msg['request'],
                                req_id=msg['req_id'],
                                server_meta=dict(user_id=self.session.user_profile.id,
                                                 client_id=self.client_id,
                                                 return_queue=tornado_return_queue_name(self.port),
                                                 log_data=log_data,
                                                 request_environ=request_environ)))

    def on_close(self) -> None:
        log_data = dict(extra='[transport=%s]' % (self.session.transport_name,))
        record_request_start_data(log_data)
        if self.close_info is not None:
            write_log_line(log_data, path='/socket/close', method='SOCKET',
                           remote_ip=self.session.conn_info.ip, email='unknown',
                           client_name='?', status_code=self.close_info.status_code,
                           error_content=self.close_info.err_msg)
        else:
            deregister_connection(self)
            email = self.session.user_profile.email \
                if self.session.user_profile is not None else 'unknown'
            write_log_line(log_data, path='/socket/close', method='SOCKET',
                           remote_ip=self.session.conn_info.ip, email=email,
                           client_name='?')

        self.did_close = True

def respond_send_message(data: Mapping[str, Any]) -> None:
    log_data = data['server_meta']['log_data']
    record_request_restart_data(log_data)

    worker_log_data = data['server_meta']['worker_log_data']
    forward_queue_delay = worker_log_data['time_started'] - log_data['time_stopped']
    return_queue_delay = log_data['time_restarted'] - data['server_meta']['time_request_finished']
    service_time = data['server_meta']['time_request_finished'] - worker_log_data['time_started']
    log_data['extra'] += ', queue_delay: %s/%s, service_time: %s]' % (
        format_timedelta(forward_queue_delay), format_timedelta(return_queue_delay),
        format_timedelta(service_time))

    client_id = data['server_meta']['client_id']
    connection = get_connection(client_id)
    if connection is None:
        logger.info("Could not find connection to send response to! client_id=%s" % (client_id,))
    else:
        connection.session.send_message({'req_id': data['req_id'], 'type': 'response',
                                         'response': data['response']})

        # TODO: Fill in client name
        # TODO: Maybe fill in the status code correctly
        write_log_line(log_data, path='/socket/service_request', method='SOCKET',
                       remote_ip=connection.session.conn_info.ip,
                       email=connection.session.user_profile.email, client_name='?')

# We disable the eventsource and htmlfile transports because they cannot
# securely send us the zulip.com cookie, which we use as part of our
# authentication scheme.
sockjs_url = '%s/static/third/sockjs/sockjs-0.3.4.js' % (settings.ROOT_DOMAIN_URI,)
sockjs_router = sockjs.tornado.SockJSRouter(SocketConnection, "/sockjs",
                                            {'sockjs_url': sockjs_url,
                                             'disabled_transports': ['eventsource', 'htmlfile']})
def get_sockjs_router(port: int) -> sockjs.tornado.SockJSRouter:
    sockjs_router._connection.port = port
    return sockjs_router

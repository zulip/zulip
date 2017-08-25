# -*- coding: utf-8 -*-

"""WebSocketBaseTestCase is based on combination of Tornado
and Django test systems. It require to use decorator '@gen.coroutine'
for each test case method( see documentation: http://www.tornadoweb.org/en/stable/testing.html).
It requires implementation of 'get_app' method to initialize tornado application and launch it.
"""
from __future__ import absolute_import
from __future__ import print_function


import time

import ujson
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.db import close_old_connections
from django.core import signals
from tornado.gen import Return
from tornado.httpclient import HTTPRequest, HTTPResponse

from zerver.lib.test_helpers import POSTRequestMock
from zerver.lib.test_classes import ZulipTestCase

from zerver.models import UserProfile, get_client

from tornado import gen
from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.web import Application
from tornado.websocket import websocket_connect

from zerver.tornado.application import create_tornado_application
from zerver.tornado import event_queue
from zerver.tornado.event_queue import fetch_events, \
    allocate_client_descriptor, process_event
from zerver.tornado.views import get_events_backend

from six.moves.http_cookies import SimpleCookie
from six.moves import urllib_parse

from typing import Any, Callable, Dict, Generator, Optional, Text, List, cast

class TornadoWebTestCase(AsyncHTTPTestCase, ZulipTestCase):
    def setUp(self):
        # type: () -> None
        super(TornadoWebTestCase, self).setUp()
        signals.request_started.disconnect(close_old_connections)
        signals.request_finished.disconnect(close_old_connections)
        self.session_cookie = None  # type: Optional[Dict[Text, Text]]

    def tearDown(self):
        # type: () -> None
        super(TornadoWebTestCase, self).tearDown()
        self.session_cookie = None  # type: Optional[Dict[Text, Text]]

    def get_app(self):
        # type: () -> Application
        return create_tornado_application()

    def client_get(self, path, **kwargs):
        # type: (Text, **Any) -> HTTPResponse
        self.add_session_cookie(kwargs)
        self.set_http_host(kwargs)
        if 'HTTP_HOST' in kwargs:
            kwargs['headers']['Host'] = kwargs['HTTP_HOST']
            del kwargs['HTTP_HOST']
        return self.fetch(path, method='GET', **kwargs)

    def fetch_async(self, method, path, **kwargs):
        # type: (Text, Text, **Any) -> None
        self.add_session_cookie(kwargs)
        self.set_http_host(kwargs)
        if 'HTTP_HOST' in kwargs:
            kwargs['headers']['Host'] = kwargs['HTTP_HOST']
            del kwargs['HTTP_HOST']
        self.http_client.fetch(
            self.get_url(path),
            self.stop,
            method=method,
            **kwargs
        )

    def client_get_async(self, path, **kwargs):
        # type: (Text, **Any) -> None
        self.set_http_host(kwargs)
        self.fetch_async('GET', path, **kwargs)

    def login(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        super(TornadoWebTestCase, self).login(*args, **kwargs)
        session_cookie = settings.SESSION_COOKIE_NAME
        session_key = self.client.session.session_key
        self.session_cookie = {
            "Cookie": "{}={}".format(session_cookie, session_key)
        }

    def get_session_cookie(self):
        # type: () -> Dict[Text, Text]
        return {} if self.session_cookie is None else self.session_cookie

    def add_session_cookie(self, kwargs):
        # type: (Dict[str, Any]) -> None
        # TODO: Currently only allows session cookie
        headers = kwargs.get('headers', {})
        headers.update(self.get_session_cookie())
        kwargs['headers'] = headers

    def create_queue(self, **kwargs):
        # type: (**Any) -> str
        response = self.client_get('/json/events?dont_block=true', subdomain="zulip")
        self.assertEqual(response.code, 200)
        body = ujson.loads(response.body)
        self.assertEqual(body['events'], [])
        self.assertIn('queue_id', body)
        return body['queue_id']

class EventsTestCase(TornadoWebTestCase):
    def test_create_queue(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        queue_id = self.create_queue()
        self.assertIn(queue_id, event_queue.clients)

    def test_events_async(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        event_queue_id = self.create_queue()
        data = {
            'queue_id': event_queue_id,
            'last_event_id': 0,
        }

        path = '/json/events?{}'.format(urllib_parse.urlencode(data))
        self.client_get_async(path)

        def process_events():
            # type: () -> None
            users = [user_profile.id]
            event = dict(
                type='test',
                data='test data',
            )
            process_event(event, users)

        self.io_loop.call_later(0.1, process_events)
        response = self.wait()
        data = ujson.loads(response.body)
        events = data['events']
        events = cast(List[Dict[str, Any]], events)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['data'], 'test data')
        self.assertEqual(data['result'], 'success')

class WebSocketBaseTestCase(AsyncHTTPTestCase, ZulipTestCase):

    def setUp(self):
        # type: () -> None
        settings.RUNNING_INSIDE_TORNADO = True
        super(WebSocketBaseTestCase, self).setUp()

    def tearDown(self):
        # type: () -> None
        super(WebSocketBaseTestCase, self).setUp()
        settings.RUNNING_INSIDE_TORNADO = False

    @gen.coroutine
    def ws_connect(self, path, cookie_header, compression_options=None):
        # type: (str, str, Optional[Any]) -> Generator[Any, Callable[[HTTPRequest, Optional[Any]], Any], None]
        request = HTTPRequest(url='ws://127.0.0.1:%d%s' % (self.get_http_port(), path))
        request.headers.add('Cookie', cookie_header)
        ws = yield websocket_connect(
            request,
            compression_options=compression_options)
        raise gen.Return(ws)

    @gen.coroutine
    def close(self, ws):
        # type: (Any) -> None
        """Close a websocket connection and wait for the server side.

        If we don't wait here, there are sometimes leak warnings in the
        tests.
        """
        ws.close()
        self.wait()

class TornadoTestCase(WebSocketBaseTestCase):
    def get_app(self):
        # type: () -> Application
        """ Return tornado app to launch for test cases
        """
        return create_tornado_application()

    @staticmethod
    def tornado_call(view_func, user_profile, post_data):
        # type: (Callable[[HttpRequest, UserProfile], HttpResponse], UserProfile, Dict[str, Any]) -> HttpResponse
        request = POSTRequestMock(post_data, user_profile)
        return view_func(request, user_profile)

    @staticmethod
    def get_cookie_header(cookies):
        # type: (Dict[Any, Any]) -> str
        return ';'.join(
            ["{}={}".format(name, value.value) for name, value in cookies.items()])

    def _get_cookies(self, user_profile):
        # type: (UserProfile) -> SimpleCookie
        resp = self.login_with_return(user_profile.email)
        return resp.cookies

    @gen.coroutine
    def _websocket_auth(self, ws, queue_events_data, cookies):
        # type: (Any, Dict[str, Dict[str, str]], SimpleCookie) -> Generator[str, str, None]
        auth_queue_id = ':'.join((queue_events_data['response']['queue_id'], '0'))
        message = {
            "req_id": auth_queue_id,
            "type": "auth",
            "request": {
                "csrf_token": cookies.get('csrftoken').coded_value,
                "queue_id": queue_events_data['response']['queue_id'],
                "status_inquiries": []
            }
        }
        auth_frame_str = ujson.dumps(message)
        ws.write_message(ujson.dumps([auth_frame_str]))
        response_ack = yield ws.read_message()
        response_message = yield ws.read_message()
        raise gen.Return([response_ack, response_message])

    @staticmethod
    def _get_queue_events_data(email):
        # type: (Text) -> Dict[str, Dict[str, str]]
        user_profile = UserProfile.objects.filter(email=email).first()
        events_query = {
            'queue_id': None,
            'narrow': [],
            'handler_id': 0,
            'user_profile_email': user_profile.email,
            'all_public_streams': False,
            'client_type_name': 'website',
            'new_queue_data': {
                'apply_markdown': True,
                'narrow': [],
                'user_profile_email': user_profile.email,
                'all_public_streams': False,
                'realm_id': user_profile.realm_id,
                'client_type_name': 'website',
                'event_types': None,
                'user_profile_id': user_profile.id,
                'queue_timeout': 0,
                'last_connection_time': time.time()},
            'last_event_id': -1,
            'event_types': None,
            'user_profile_id': user_profile.id,
            'dont_block': True,
            'lifespan_secs': 0
        }
        result = fetch_events(events_query)
        return result

    def _check_message_sending(self, request_id, ack_resp, msg_resp, profile, queue_events_data):
        # type: (str, str, str, UserProfile, Dict[str, Dict[str, str]]) -> None
        self.assertEqual(ack_resp[0], 'a')
        self.assertEqual(
            ujson.loads(ack_resp[1:]),
            [
                {
                    "type": "ack",
                    "req_id": request_id
                }
            ])
        self.assertEqual(msg_resp[0], 'a')
        result = self.tornado_call(get_events_backend, profile,
                                   {"queue_id": queue_events_data['response']['queue_id'],
                                    "user_client": "website",
                                    "last_event_id": -1,
                                    "dont_block": ujson.dumps(True),
                                    })
        result_content = ujson.loads(result.content)
        self.assertEqual(len(result_content['events']), 1)
        message_id = result_content['events'][0]['message']['id']
        self.assertEqual(
            ujson.loads(msg_resp[1:]),
            [
                {
                    "type": "response",
                    "response":
                        {
                            "result": "success",
                            "id": message_id,
                            "msg": ""
                        },
                    "req_id": request_id
                }
            ])

    @gen_test
    def test_tornado_connect(self):
        # type: () -> Generator[str, Any, None]
        user_profile = self.example_user('hamlet')
        cookies = self._get_cookies(user_profile)
        cookie_header = self.get_cookie_header(cookies)
        ws = yield self.ws_connect('/sockjs/366/v8nw22qe/websocket', cookie_header=cookie_header)
        response = yield ws.read_message()
        self.assertEqual(response, 'o')
        self.close(ws)

    @gen_test
    def test_tornado_auth(self):
        # type: () -> Generator[str, TornadoTestCase, None]
        user_profile = self.example_user('hamlet')
        cookies = self._get_cookies(user_profile)
        cookie_header = self.get_cookie_header(cookies)
        ws = yield self.ws_connect('/sockjs/366/v8nw22qe/websocket', cookie_header=cookie_header)
        yield ws.read_message()
        queue_events_data = self._get_queue_events_data(user_profile.email)
        request_id = ':'.join((queue_events_data['response']['queue_id'], '0'))
        response = yield self._websocket_auth(ws, queue_events_data, cookies)
        self.assertEqual(response[0][0], 'a')
        self.assertEqual(
            ujson.loads(response[0][1:]),
            [
                {
                    "type": "ack",
                    "req_id": request_id
                }
            ])
        self.assertEqual(response[1][0], 'a')
        self.assertEqual(
            ujson.loads(response[1][1:]),
            [
                {"req_id": request_id,
                 "response": {
                     "result": "success",
                     "status_inquiries": {},
                     "msg": ""
                 },
                 "type": "response"}
            ])
        self.close(ws)

    @gen_test
    def test_sending_private_message(self):
        # type: () -> Generator[str, Any, None]
        user_profile = self.example_user('hamlet')
        cookies = self._get_cookies(user_profile)
        cookie_header = self.get_cookie_header(cookies)
        queue_events_data = self._get_queue_events_data(user_profile.email)
        ws = yield self.ws_connect('/sockjs/366/v8nw22qe/websocket', cookie_header=cookie_header)
        yield ws.read_message()
        yield self._websocket_auth(ws, queue_events_data, cookies)
        request_id = ':'.join((queue_events_data['response']['queue_id'], '1'))
        user_message = {
            "req_id": request_id,
            "type": "request",
            "request": {
                "client": "website",
                "type": "private",
                "subject": "(no topic)",
                "stream": "",
                "private_message_recipient": self.example_email('othello'),
                "content": "hello",
                "sender_id": user_profile.id,
                "queue_id": queue_events_data['response']['queue_id'],
                "to": ujson.dumps([self.example_email('othello')]),
                "reply_to": self.example_email('hamlet'),
                "local_id": -1
            }
        }
        user_message_str = ujson.dumps(user_message)
        ws.write_message(ujson.dumps([user_message_str]))
        ack_resp = yield ws.read_message()
        msg_resp = yield ws.read_message()
        self._check_message_sending(request_id, ack_resp, msg_resp, user_profile, queue_events_data)
        self.close(ws)

    @gen_test
    def test_sending_stream_message(self):
        # type: () -> Generator[str, Any, None]
        user_profile = self.example_user('hamlet')
        cookies = self._get_cookies(user_profile)
        cookie_header = self.get_cookie_header(cookies)
        queue_events_data = self._get_queue_events_data(user_profile.email)
        ws = yield self.ws_connect('/sockjs/366/v8nw22qe/websocket', cookie_header=cookie_header)
        yield ws.read_message()
        yield self._websocket_auth(ws, queue_events_data, cookies)
        request_id = ':'.join((queue_events_data['response']['queue_id'], '1'))
        user_message = {
            "req_id": request_id,
            "type": "request",
            "request": {
                "client": "website",
                "type": "stream",
                "subject": "Stream message",
                "stream": "Denmark",
                "private_message_recipient": "",
                "content": "hello",
                "sender_id": user_profile.id,
                "queue_id": queue_events_data['response']['queue_id'],
                "to": ujson.dumps(["Denmark"]),
                "reply_to": self.example_email('hamlet'),
                "local_id": -1
            }
        }
        user_message_str = ujson.dumps(user_message)
        ws.write_message(ujson.dumps([user_message_str]))
        ack_resp = yield ws.read_message()
        msg_resp = yield ws.read_message()
        self._check_message_sending(request_id, ack_resp, msg_resp, user_profile, queue_events_data)
        self.close(ws)

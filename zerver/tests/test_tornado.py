import urllib.parse
from typing import Any, Dict, Optional

import orjson
from django.conf import settings
from django.core import signals
from django.db import close_old_connections
from django.test import override_settings
from tornado.httpclient import HTTPResponse
from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

from zerver.lib.test_classes import ZulipTestCase
from zerver.tornado import event_queue
from zerver.tornado.application import create_tornado_application
from zerver.tornado.event_queue import process_event


class TornadoWebTestCase(AsyncHTTPTestCase, ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        signals.request_started.disconnect(close_old_connections)
        signals.request_finished.disconnect(close_old_connections)
        self.session_cookie: Optional[Dict[str, str]] = None

    def tearDown(self) -> None:
        super().tearDown()
        self.session_cookie = None

    @override_settings(DEBUG=False)
    def get_app(self) -> Application:
        return create_tornado_application()

    def tornado_client_get(self, path: str, **kwargs: Any) -> HTTPResponse:
        self.add_session_cookie(kwargs)
        kwargs['skip_user_agent'] = True
        self.set_http_headers(kwargs)
        if 'HTTP_HOST' in kwargs:
            kwargs['headers']['Host'] = kwargs['HTTP_HOST']
            del kwargs['HTTP_HOST']
        return self.fetch(path, method='GET', **kwargs)

    def fetch_async(self, method: str, path: str, **kwargs: Any) -> None:
        self.add_session_cookie(kwargs)
        kwargs['skip_user_agent'] = True
        self.set_http_headers(kwargs)
        if 'HTTP_HOST' in kwargs:
            kwargs['headers']['Host'] = kwargs['HTTP_HOST']
            del kwargs['HTTP_HOST']
        self.http_client.fetch(
            self.get_url(path),
            self.stop,
            method=method,
            **kwargs,
        )

    def client_get_async(self, path: str, **kwargs: Any) -> None:
        kwargs['skip_user_agent'] = True
        self.set_http_headers(kwargs)
        self.fetch_async('GET', path, **kwargs)

    def login_user(self, *args: Any, **kwargs: Any) -> None:
        super().login_user(*args, **kwargs)
        session_cookie = settings.SESSION_COOKIE_NAME
        session_key = self.client.session.session_key
        self.session_cookie = {
            "Cookie": f"{session_cookie}={session_key}",
        }

    def get_session_cookie(self) -> Dict[str, str]:
        return {} if self.session_cookie is None else self.session_cookie

    def add_session_cookie(self, kwargs: Dict[str, Any]) -> None:
        # TODO: Currently only allows session cookie
        headers = kwargs.get('headers', {})
        headers.update(self.get_session_cookie())
        kwargs['headers'] = headers

    def create_queue(self, **kwargs: Any) -> str:
        response = self.tornado_client_get(
            '/json/events?dont_block=true',
            subdomain="zulip",
            skip_user_agent=True,
        )
        self.assertEqual(response.code, 200)
        body = orjson.loads(response.body)
        self.assertEqual(body['events'], [])
        self.assertIn('queue_id', body)
        return body['queue_id']

class EventsTestCase(TornadoWebTestCase):
    def test_create_queue(self) -> None:
        self.login_user(self.example_user('hamlet'))
        queue_id = self.create_queue()
        self.assertIn(queue_id, event_queue.clients)

    def test_events_async(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        event_queue_id = self.create_queue()
        data = {
            'queue_id': event_queue_id,
            'last_event_id': -1,
        }

        path = f'/json/events?{urllib.parse.urlencode(data)}'
        self.client_get_async(path)

        def process_events() -> None:
            users = [user_profile.id]
            event = dict(
                type='test',
                data='test data',
            )
            process_event(event, users)

        self.io_loop.call_later(0.1, process_events)
        response = self.wait()
        data = orjson.loads(response.body)
        self.assertEqual(data['events'], [
            {'type': 'test', 'data': 'test data', 'id': 0},
        ])
        self.assertEqual(data['result'], 'success')

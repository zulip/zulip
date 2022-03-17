import asyncio
import urllib.parse
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar
from unittest import TestResult

import orjson
from asgiref.sync import async_to_sync, sync_to_async
from django.conf import settings
from django.core import signals
from django.db import close_old_connections
from django.test import override_settings
from tornado.httpclient import HTTPResponse
from tornado.ioloop import IOLoop
from tornado.platform.asyncio import AsyncIOMainLoop
from tornado.testing import AsyncHTTPTestCase, AsyncTestCase
from tornado.web import Application
from typing_extensions import ParamSpec

from zerver.lib.test_classes import ZulipTestCase
from zerver.tornado import event_queue
from zerver.tornado.application import create_tornado_application
from zerver.tornado.event_queue import process_event

P = ParamSpec("P")
T = TypeVar("T")


def async_to_sync_decorator(f: Callable[P, Awaitable[T]]) -> Callable[P, T]:
    @wraps(f)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        return async_to_sync(f)(*args, **kwargs)

    return wrapped


async def in_django_thread(f: Callable[[], T]) -> T:
    return await asyncio.create_task(sync_to_async(f)())


class TornadoWebTestCase(AsyncHTTPTestCase, ZulipTestCase):
    @async_to_sync_decorator
    async def setUp(self) -> None:
        super().setUp()
        signals.request_started.disconnect(close_old_connections)
        signals.request_finished.disconnect(close_old_connections)
        self.session_cookie: Optional[Dict[str, str]] = None

    @async_to_sync_decorator
    async def tearDown(self) -> None:
        # Skip tornado.testing.AsyncTestCase.tearDown because it tries to kill
        # the current task.
        super(AsyncTestCase, self).tearDown()

    def run(self, result: Optional[TestResult] = None) -> Optional[TestResult]:
        return async_to_sync(
            sync_to_async(super().run, thread_sensitive=False), force_new_loop=True
        )(result)

    def get_new_ioloop(self) -> IOLoop:
        return AsyncIOMainLoop()

    @override_settings(DEBUG=False)
    def get_app(self) -> Application:
        return create_tornado_application()

    async def tornado_client_get(self, path: str, **kwargs: Any) -> HTTPResponse:
        self.add_session_cookie(kwargs)
        kwargs["skip_user_agent"] = True
        self.set_http_headers(kwargs)
        if "HTTP_HOST" in kwargs:
            kwargs["headers"]["Host"] = kwargs["HTTP_HOST"]
            del kwargs["HTTP_HOST"]
        return await self.http_client.fetch(self.get_url(path), method="GET", **kwargs)

    async def fetch_async(self, method: str, path: str, **kwargs: Any) -> HTTPResponse:
        self.add_session_cookie(kwargs)
        kwargs["skip_user_agent"] = True
        self.set_http_headers(kwargs)
        if "HTTP_HOST" in kwargs:
            kwargs["headers"]["Host"] = kwargs["HTTP_HOST"]
            del kwargs["HTTP_HOST"]
        return await self.http_client.fetch(self.get_url(path), method=method, **kwargs)

    async def client_get_async(self, path: str, **kwargs: Any) -> HTTPResponse:
        kwargs["skip_user_agent"] = True
        self.set_http_headers(kwargs)
        return await self.fetch_async("GET", path, **kwargs)

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
        headers = kwargs.get("headers", {})
        headers.update(self.get_session_cookie())
        kwargs["headers"] = headers

    async def create_queue(self, **kwargs: Any) -> str:
        response = await self.tornado_client_get(
            "/json/events?dont_block=true",
            subdomain="zulip",
            skip_user_agent=True,
        )
        self.assertEqual(response.code, 200)
        body = orjson.loads(response.body)
        self.assertEqual(body["events"], [])
        self.assertIn("queue_id", body)
        return body["queue_id"]


class EventsTestCase(TornadoWebTestCase):
    @async_to_sync_decorator
    async def test_create_queue(self) -> None:
        await in_django_thread(lambda: self.login_user(self.example_user("hamlet")))
        queue_id = await self.create_queue()
        self.assertIn(queue_id, event_queue.clients)

    @async_to_sync_decorator
    async def test_events_async(self) -> None:
        user_profile = await in_django_thread(lambda: self.example_user("hamlet"))
        await in_django_thread(lambda: self.login_user(user_profile))
        event_queue_id = await self.create_queue()
        data = {
            "queue_id": event_queue_id,
            "last_event_id": -1,
        }

        path = f"/json/events?{urllib.parse.urlencode(data)}"

        def process_events() -> None:
            users = [user_profile.id]
            event = dict(
                type="test",
                data="test data",
            )
            process_event(event, users)

        self.io_loop.call_later(0.1, process_events)
        response = await self.client_get_async(path)
        self.assertEqual(response.headers["Vary"], "Accept-Language, Cookie")
        data = orjson.loads(response.body)
        self.assertEqual(
            data["events"],
            [
                {"type": "test", "data": "test data", "id": 0},
            ],
        )
        self.assertEqual(data["result"], "success")

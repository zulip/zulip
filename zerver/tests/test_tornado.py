import asyncio
import socket
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, TypeVar
from unittest import mock
from urllib.parse import urlencode

import orjson
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core import signals
from django.db import close_old_connections
from django.test import override_settings
from tornado import netutil
from tornado.httpclient import AsyncHTTPClient, HTTPResponse
from tornado.httpserver import HTTPServer
from typing_extensions import override

from zerver.lib.cache import user_profile_narrow_by_id_cache_key
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import cache_tries_captured, queries_captured
from zerver.models import UserProfile
from zerver.tornado import event_queue
from zerver.tornado.application import create_tornado_application
from zerver.tornado.event_queue import process_event

T = TypeVar("T")


class TornadoWebTestCase(ZulipTestCase):
    @asynccontextmanager
    async def with_tornado(self) -> AsyncIterator[None]:
        super().setUp()

        with override_settings(DEBUG=False):
            self.http_server = HTTPServer(create_tornado_application())
        sock = netutil.bind_sockets(0, "127.0.0.1", family=socket.AF_INET)[0]
        self.port = sock.getsockname()[1]
        self.http_server.add_sockets([sock])
        self.http_client = AsyncHTTPClient()
        signals.request_started.disconnect(close_old_connections)
        signals.request_finished.disconnect(close_old_connections)
        self.session_cookie: dict[str, str] | None = None
        try:
            yield
        finally:
            self.http_client.close()
            self.http_server.stop()
            await self.http_server.close_all_connections()
            tasks = set(asyncio.all_tasks()) - {asyncio.current_task()}
            if tasks:  # nocoverage
                await asyncio.wait(tasks)

    async def fetch_async(self, method: str, path: str, **kwargs: Any) -> HTTPResponse:
        self.add_session_cookie(kwargs)
        self.set_http_headers(kwargs, skip_user_agent=True)
        if "HTTP_HOST" in kwargs:
            kwargs["headers"]["Host"] = kwargs["HTTP_HOST"]
            del kwargs["HTTP_HOST"]
        return await self.http_client.fetch(
            f"http://127.0.0.1:{self.port}{path}", method=method, **kwargs
        )

    @override
    def login_user(self, *args: Any, **kwargs: Any) -> None:
        super().login_user(*args, **kwargs)
        session_cookie = settings.SESSION_COOKIE_NAME
        session_key = self.client.session.session_key
        self.session_cookie = {
            "Cookie": f"{session_cookie}={session_key}",
        }

    def get_session_cookie(self) -> dict[str, str]:
        return {} if self.session_cookie is None else self.session_cookie

    def add_session_cookie(self, kwargs: dict[str, Any]) -> None:
        # TODO: Currently only allows session cookie
        headers = kwargs.get("headers", {})
        headers.update(self.get_session_cookie())
        kwargs["headers"] = headers

    async def create_queue(self, **kwargs: Any) -> str:
        response = await self.fetch_async("GET", "/json/events?dont_block=true", subdomain="zulip")
        self.assertEqual(response.code, 200)
        body = orjson.loads(response.body)
        self.assertEqual(body["events"], [])
        self.assertIn("queue_id", body)
        return body["queue_id"]


class EventsTestCase(TornadoWebTestCase):
    async def test_create_queue(self) -> None:
        async with self.with_tornado():
            await sync_to_async(lambda: self.login_user(self.example_user("hamlet")))()
            queue_id = await self.create_queue()
            self.assertIn(queue_id, event_queue.clients)

    @contextmanager
    def mocked_events(self, user_profile: UserProfile, event: dict[str, object]) -> Iterator[None]:
        def process_events() -> None:
            users = [user_profile.id]
            process_event(event, users)

        def wrapped_fetch_events(**query: Any) -> dict[str, Any]:
            ret = event_queue.fetch_events(**query)
            asyncio.get_running_loop().call_soon(process_events)
            return ret

        with mock.patch("zerver.tornado.views.fetch_events", side_effect=wrapped_fetch_events):
            yield

    async def test_events_async(self) -> None:
        async with self.with_tornado():
            user_profile = await sync_to_async(lambda: self.example_user("hamlet"))()
            await sync_to_async(lambda: self.login_user(user_profile))()
            event_queue_id = await self.create_queue()
            data = {
                "queue_id": event_queue_id,
                "last_event_id": -1,
            }

            path = f"/json/events?{urlencode(data)}"

            with self.mocked_events(user_profile, {"type": "test", "data": "test data"}):
                response = await self.fetch_async("GET", path)

            self.assertEqual(response.headers["Vary"], "Accept-Language, Cookie")
            data = orjson.loads(response.body)
            self.assertEqual(
                data["events"],
                [
                    {"type": "test", "data": "test data", "id": 0},
                ],
            )
            self.assertEqual(data["result"], "success")

    async def test_events_caching(self) -> None:
        async with self.with_tornado():
            user_profile = await sync_to_async(lambda: self.example_user("hamlet"))()
            await sync_to_async(lambda: self.login_user(user_profile))()
            event_queue_id = await self.create_queue()
            data = {
                "queue_id": event_queue_id,
                "last_event_id": -1,
            }

            path = f"/json/events?{urlencode(data)}"

            with (
                self.mocked_events(user_profile, {"type": "test", "data": "test data"}),
                cache_tries_captured() as cache_gets,
                queries_captured() as queries,
            ):
                await self.fetch_async("GET", path)

                # Two cache fetches -- for the user and the client.  In
                # production, the session would also be a cache access,
                # but tests don't use cached sessions.
                self.assert_length(cache_gets, 2)
                self.assertEqual(
                    cache_gets[0],
                    ("get", user_profile_narrow_by_id_cache_key(user_profile.id), None),
                )
                self.assertEqual(cache_gets[1][0], "get")
                assert isinstance(cache_gets[1][1], str)
                self.assertTrue(cache_gets[1][1].startswith("get_client:"))

                # Three database queries -- session, user, and client.
                # The user query should remain small; it is currently 470
                # bytes, but anything under 1k should be Fine.
                self.assert_length(queries, 3)
                self.assertIn("django_session", queries[0].sql)
                self.assertIn("zerver_userprofile", queries[1].sql)
                self.assertLessEqual(len(queries[1].sql), 1024)
                self.assertIn("zerver_client", queries[2].sql)

            # Perform the same request again, preserving the caches.  We
            # should only see one database query -- the session.  As noted
            # above, in production even that would be cached.
            with (
                self.mocked_events(user_profile, {"type": "test", "data": "test data"}),
                cache_tries_captured() as cache_gets,
                queries_captured(keep_cache_warm=True) as queries,
            ):
                await self.fetch_async("GET", path)
                self.assert_length(cache_gets, 1)
                self.assertEqual(
                    cache_gets[0],
                    ("get", user_profile_narrow_by_id_cache_key(user_profile.id), None),
                )
                # Client is cached in-process-memory, so doesn't even see
                # a memcached hit

                self.assert_length(queries, 1)
                self.assertIn("django_session", queries[0].sql)

import time
from contextlib import contextmanager
from typing import Callable, Iterator, Optional
from unittest import mock, skipUnless

import DNS
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.utils.timezone import now as timezone_now

from zerver.forms import email_is_not_mit_mailing_list
from zerver.lib.rate_limiter import (
    RateLimitedIPAddr,
    RateLimitedUser,
    RateLimiterLockingException,
    add_ratelimit_rule,
    remove_ratelimit_rule,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.zephyr import compute_mit_user_fullname
from zerver.models import PushDeviceToken, UserProfile

if settings.ZILENCER_ENABLED:
    from zilencer.models import RateLimitedRemoteZulipServer, RemoteZulipServer


class MITNameTest(ZulipTestCase):
    def test_valid_hesiod(self) -> None:
        with mock.patch(
            "DNS.dnslookup",
            return_value=[
                ["starnine:*:84233:101:Athena Consulting Exchange User,,,:/mit/starnine:/bin/bash"]
            ],
        ):
            self.assertEqual(
                compute_mit_user_fullname(self.mit_email("starnine")),
                "Athena Consulting Exchange User",
            )
        with mock.patch(
            "DNS.dnslookup",
            return_value=[["sipbexch:*:87824:101:Exch Sipb,,,:/mit/sipbexch:/bin/athena/bash"]],
        ):
            self.assertEqual(compute_mit_user_fullname("sipbexch@mit.edu"), "Exch Sipb")

    def test_invalid_hesiod(self) -> None:
        with mock.patch(
            "DNS.dnslookup", side_effect=DNS.Base.ServerError("DNS query status: NXDOMAIN", 3)
        ):
            self.assertEqual(compute_mit_user_fullname("1234567890@mit.edu"), "1234567890@mit.edu")
        with mock.patch(
            "DNS.dnslookup", side_effect=DNS.Base.ServerError("DNS query status: NXDOMAIN", 3)
        ):
            self.assertEqual(compute_mit_user_fullname("ec-discuss@mit.edu"), "ec-discuss@mit.edu")

    def test_mailinglist(self) -> None:
        with mock.patch(
            "DNS.dnslookup", side_effect=DNS.Base.ServerError("DNS query status: NXDOMAIN", 3)
        ):
            self.assertRaises(ValidationError, email_is_not_mit_mailing_list, "1234567890@mit.edu")
        with mock.patch(
            "DNS.dnslookup", side_effect=DNS.Base.ServerError("DNS query status: NXDOMAIN", 3)
        ):
            self.assertRaises(ValidationError, email_is_not_mit_mailing_list, "ec-discuss@mit.edu")

    def test_notmailinglist(self) -> None:
        with mock.patch("DNS.dnslookup", return_value=[["POP IMAP.EXCHANGE.MIT.EDU starnine"]]):
            email_is_not_mit_mailing_list("sipbexch@mit.edu")


@contextmanager
def rate_limit_rule(range_seconds: int, num_requests: int, domain: str) -> Iterator[None]:
    add_ratelimit_rule(range_seconds, num_requests, domain=domain)
    try:
        yield
    finally:
        # We need this in a finally block to ensure the test cleans up after itself
        # even in case of failure, to avoid polluting the rules state.
        remove_ratelimit_rule(range_seconds, num_requests, domain=domain)


class RateLimitTests(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()

        # Some tests here can be somewhat timing-sensitive in a way
        # that can't be eliminated, e.g. due to testing things that rely
        # on Redis' internal timing mechanism which we can't mock.
        # The first API request when running a suite of tests is slow
        # and can take multiple seconds. This is not a problem when running
        # multiple tests, but if an individual, time-sensitive test from this class
        # is run, the first API request it makes taking a lot of time can throw things off
        # and cause the test to fail. Thus we do a dummy API request here to warm up
        # the system and allow the tests to assume their requests won't take multiple seconds.
        user = self.example_user("hamlet")
        self.api_get(user, "/api/v1/messages")

        settings.RATE_LIMITING = True
        add_ratelimit_rule(1, 5)

    def tearDown(self) -> None:
        settings.RATE_LIMITING = False
        remove_ratelimit_rule(1, 5)

        super().tearDown()

    def send_api_message(self, user: UserProfile, content: str) -> HttpResponse:
        return self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "stream",
                "to": "Verona",
                "client": "test suite",
                "content": content,
                "topic": "whatever",
            },
        )

    def send_unauthed_api_request(self) -> HttpResponse:
        result = self.client_get("/json/messages")
        # We're not making a correct request here, but rate-limiting is supposed
        # to happen before the request fails due to not being correctly made. Thus
        # we expect either an 400 error if the request is allowed by the rate limiter,
        # or 429 if we're above the limit. We don't expect to see other status codes here,
        # so we assert for safety.
        self.assertIn(result.status_code, [400, 429])
        return result

    def test_headers(self) -> None:
        user = self.example_user("hamlet")
        RateLimitedUser(user).clear_history()

        result = self.send_api_message(user, "some stuff")
        self.assertTrue("X-RateLimit-Remaining" in result)
        self.assertTrue("X-RateLimit-Limit" in result)
        self.assertTrue("X-RateLimit-Reset" in result)

    def test_ratelimit_decrease(self) -> None:
        user = self.example_user("hamlet")
        RateLimitedUser(user).clear_history()
        result = self.send_api_message(user, "some stuff")
        limit = int(result["X-RateLimit-Remaining"])

        result = self.send_api_message(user, "some stuff 2")
        newlimit = int(result["X-RateLimit-Remaining"])
        self.assertEqual(limit, newlimit + 1)

    def do_test_hit_ratelimits(
        self,
        request_func: Callable[[], HttpResponse],
        assert_func: Optional[Callable[[HttpResponse], None]] = None,
    ) -> HttpResponse:
        def default_assert_func(result: HttpResponse) -> None:
            self.assertEqual(result.status_code, 429)
            json = result.json()
            self.assertEqual(json.get("result"), "error")
            self.assertIn("API usage exceeded rate limit", json.get("msg"))
            self.assertEqual(json.get("retry-after"), 0.5)
            self.assertTrue("Retry-After" in result)
            self.assertEqual(result["Retry-After"], "0.5")

        if assert_func is None:
            assert_func = default_assert_func

        start_time = time.time()
        for i in range(6):
            with mock.patch("time.time", return_value=(start_time + i * 0.1)):
                result = request_func()
            if i < 5:
                self.assertNotEqual(result.status_code, 429)

        assert_func(result)

        # We simulate waiting a second here, rather than force-clearing our history,
        # to make sure the rate-limiting code automatically forgives a user
        # after some time has passed.
        with mock.patch("time.time", return_value=(start_time + 1.01)):
            result = request_func()

            self.assertNotEqual(result, 429)

    def test_hit_ratelimits_as_user(self) -> None:
        user = self.example_user("cordelia")
        RateLimitedUser(user).clear_history()

        self.do_test_hit_ratelimits(lambda: self.send_api_message(user, "some stuff"))

    @rate_limit_rule(1, 5, domain="api_by_ip")
    def test_hit_ratelimits_as_ip(self) -> None:
        RateLimitedIPAddr("127.0.0.1").clear_history()
        self.do_test_hit_ratelimits(self.send_unauthed_api_request)

    @rate_limit_rule(1, 5, domain="create_realm_by_ip")
    def test_create_realm_rate_limiting(self) -> None:
        def assert_func(result: HttpResponse) -> None:
            self.assertEqual(result.status_code, 429)
            self.assert_in_response("Rate limit exceeded.", result)

        with self.settings(OPEN_REALM_CREATION=True):
            RateLimitedIPAddr("127.0.0.1", domain="create_realm_by_ip").clear_history()
            self.do_test_hit_ratelimits(
                lambda: self.client_post("/new/", {"email": "new@zulip.com"}),
                assert_func=assert_func,
            )

    def test_find_account_rate_limiting(self) -> None:
        def assert_func(result: HttpResponse) -> None:
            self.assertEqual(result.status_code, 429)
            self.assert_in_response("Rate limit exceeded.", result)

        with rate_limit_rule(1, 5, domain="find_account_by_ip"):
            RateLimitedIPAddr("127.0.0.1", domain="find_account_by_ip").clear_history()
            self.do_test_hit_ratelimits(
                lambda: self.client_post("/accounts/find/", {"emails": "new@zulip.com"}),
                assert_func=assert_func,
            )

        # Now test whether submitting multiple emails is handled correctly.
        # The limit is set to 10 per second, so 5 requests with 2 emails
        # submitted in each should be allowed.
        with rate_limit_rule(1, 10, domain="find_account_by_ip"):
            RateLimitedIPAddr("127.0.0.1", domain="find_account_by_ip").clear_history()
            self.do_test_hit_ratelimits(
                lambda: self.client_post(
                    "/accounts/find/", {"emails": "new@zulip.com,new2@zulip.com"}
                ),
                assert_func=assert_func,
            )

    @skipUnless(settings.ZILENCER_ENABLED, "requires zilencer")
    @rate_limit_rule(1, 5, domain="api_by_remote_server")
    def test_hit_ratelimits_as_remote_server(self) -> None:
        server_uuid = "1234-abcd"
        server = RemoteZulipServer(
            uuid=server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            last_updated=timezone_now(),
        )
        server.save()

        endpoint = "/api/v1/remotes/push/register"
        payload = {"user_id": 10, "token": "111222", "token_kind": PushDeviceToken.GCM}
        try:
            # Remote servers can only make requests to the root subdomain.
            original_default_subdomain = self.DEFAULT_SUBDOMAIN
            self.DEFAULT_SUBDOMAIN = ""

            RateLimitedRemoteZulipServer(server).clear_history()
            with self.assertLogs("zerver.lib.rate_limiter", level="WARNING") as m:
                self.do_test_hit_ratelimits(lambda: self.uuid_post(server_uuid, endpoint, payload))
            self.assertEqual(
                m.output,
                [
                    "WARNING:zerver.lib.rate_limiter:Remote server <RemoteZulipServer demo.example.com 1234-abcd> exceeded rate limits on domain api_by_remote_server"
                ],
            )
        finally:
            self.DEFAULT_SUBDOMAIN = original_default_subdomain

    def test_hit_ratelimiterlockingexception(self) -> None:
        user = self.example_user("cordelia")
        RateLimitedUser(user).clear_history()

        with mock.patch(
            "zerver.lib.rate_limiter.RedisRateLimiterBackend.incr_ratelimit",
            side_effect=RateLimiterLockingException,
        ):
            with self.assertLogs("zerver.lib.rate_limiter", level="WARNING") as m:
                result = self.send_api_message(user, "some stuff")
                self.assertEqual(result.status_code, 429)
            self.assertEqual(
                m.output,
                [
                    "WARNING:zerver.lib.rate_limiter:Deadlock trying to incr_ratelimit for {}".format(
                        f"RateLimitedUser:{user.id}:api_by_user"
                    )
                ],
            )

import time
import uuid
from contextlib import contextmanager
from typing import IO, TYPE_CHECKING, Any, Callable, Iterator, Optional, Sequence
from unittest import mock, skipUnless

import DNS
import orjson
from circuitbreaker import CircuitBreakerMonitor
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils.timezone import now as timezone_now

from zerver.forms import email_is_not_mit_mailing_list
from zerver.lib.cache import cache_delete
from zerver.lib.rate_limiter import (
    RateLimitedIPAddr,
    RateLimitedUser,
    RateLimiterLockingError,
    get_tor_ips,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import ratelimit_rule
from zerver.lib.zephyr import compute_mit_user_fullname
from zerver.models import PushDeviceToken, UserProfile

if settings.ZILENCER_ENABLED:
    from zilencer.models import RateLimitedRemoteZulipServer, RemoteZulipServer

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


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

    def tearDown(self) -> None:
        settings.RATE_LIMITING = False

        super().tearDown()

    def send_api_message(self, user: UserProfile, content: str) -> "TestHttpResponse":
        return self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "stream",
                "to": orjson.dumps("Verona").decode(),
                "content": content,
                "topic": "whatever",
            },
        )

    def send_unauthed_api_request(self, **kwargs: Any) -> "TestHttpResponse":
        result = self.client_get("/json/messages", **kwargs)
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
        self.assertTrue("X-RateLimit-Remaining" in result.headers)
        self.assertTrue("X-RateLimit-Limit" in result.headers)
        self.assertTrue("X-RateLimit-Reset" in result.headers)

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
        request_func: Callable[[], "TestHttpResponse"],
        is_json: bool = True,
    ) -> None:
        def api_assert_func(result: "TestHttpResponse") -> None:
            self.assertEqual(result.status_code, 429)
            self.assertEqual(result.headers["Content-Type"], "application/json")
            json = result.json()
            self.assertEqual(json.get("result"), "error")
            self.assertIn("API usage exceeded rate limit", json.get("msg"))
            self.assertEqual(json.get("retry-after"), 0.5)
            self.assertTrue("Retry-After" in result.headers)
            self.assertEqual(result["Retry-After"], "0.5")

        def user_facing_assert_func(result: "TestHttpResponse") -> None:
            self.assertEqual(result.status_code, 429)
            self.assertNotEqual(result.headers["Content-Type"], "application/json")
            self.assert_in_response("Rate limit exceeded.", result)

        if is_json:
            assert_func = api_assert_func
        else:
            assert_func = user_facing_assert_func

        start_time = time.time()
        for i in range(6):
            with mock.patch("time.time", return_value=start_time + i * 0.1):
                result = request_func()
            if i < 5:
                self.assertNotEqual(result.status_code, 429)

        assert_func(result)

        # We simulate waiting a second here, rather than force-clearing our history,
        # to make sure the rate-limiting code automatically forgives a user
        # after some time has passed.
        with mock.patch("time.time", return_value=start_time + 1.01):
            result = request_func()

            self.assertNotEqual(result.status_code, 429)

    @ratelimit_rule(1, 5, domain="api_by_user")
    def test_hit_ratelimits_as_user(self) -> None:
        user = self.example_user("cordelia")
        RateLimitedUser(user).clear_history()

        self.do_test_hit_ratelimits(lambda: self.send_api_message(user, "some stuff"))

    @ratelimit_rule(1, 5, domain="email_change_by_user")
    def test_hit_change_email_ratelimit_as_user(self) -> None:
        user = self.example_user("cordelia")
        RateLimitedUser(user).clear_history()

        emails = ["new-email-{n}@zulip.com" for n in range(1, 8)]
        self.do_test_hit_ratelimits(
            lambda: self.api_patch(user, "/api/v1/settings", {"email": emails.pop()}),
        )

    @ratelimit_rule(1, 5, domain="api_by_ip")
    def test_hit_ratelimits_as_ip(self) -> None:
        self.do_test_hit_ratelimits(self.send_unauthed_api_request)

        # Other IPs should not be rate-limited
        resp = self.send_unauthed_api_request(REMOTE_ADDR="127.0.0.2")
        self.assertNotEqual(resp.status_code, 429)

    @ratelimit_rule(1, 5, domain="sends_email_by_ip")
    def test_create_realm_rate_limiting(self) -> None:
        with self.settings(OPEN_REALM_CREATION=True):
            self.do_test_hit_ratelimits(
                lambda: self.submit_realm_creation_form(
                    email="new@zulip.com", realm_subdomain="custom-test", realm_name="Zulip test"
                ),
                is_json=False,
            )

    @ratelimit_rule(1, 5, domain="sends_email_by_ip")
    def test_find_account_rate_limiting(self) -> None:
        self.do_test_hit_ratelimits(
            lambda: self.client_post("/accounts/find/", {"emails": "new@zulip.com"}),
            is_json=False,
        )

    @ratelimit_rule(1, 5, domain="sends_email_by_ip")
    def test_password_reset_rate_limiting(self) -> None:
        with self.assertLogs(level="INFO") as m:
            self.do_test_hit_ratelimits(
                lambda: self.client_post("/accounts/password/reset/", {"email": "new@zulip.com"}),
                is_json=False,
            )
        self.assertEqual(
            m.output,
            ["INFO:root:Too many password reset attempts for email new@zulip.com from 127.0.0.1"],
        )

    # Test whether submitting multiple emails is handled correctly.
    # The limit is set to 10 per second, so 5 requests with 2 emails
    # submitted in each should be allowed.
    @ratelimit_rule(1, 10, domain="sends_email_by_ip")
    def test_find_account_rate_limiting_multiple(self) -> None:
        self.do_test_hit_ratelimits(
            lambda: self.client_post("/accounts/find/", {"emails": "new@zulip.com,new2@zulip.com"}),
            is_json=False,
        )

    # If I submit with 3 emails and the rate-limit is 2, I should get
    # a 429 and not send any emails.
    @ratelimit_rule(1, 2, domain="sends_email_by_ip")
    def test_find_account_rate_limiting_multiple_one_request(self) -> None:
        emails = [
            "iago@zulip.com",
            "cordelia@zulip.com",
            "hamlet@zulip.com",
        ]
        resp = self.client_post("/accounts/find/", {"emails": ",".join(emails)})
        self.assertEqual(resp.status_code, 429)

        from django.core.mail import outbox

        self.assert_length(outbox, 0)

    @ratelimit_rule(1, 5, domain="sends_email_by_ip")
    def test_register_account_rate_limiting(self) -> None:
        self.do_test_hit_ratelimits(
            lambda: self.client_post("/register/", {"email": "new@zulip.com"}),
            is_json=False,
        )

    @ratelimit_rule(1, 5, domain="sends_email_by_ip")
    def test_combined_ip_limits(self) -> None:
        # Alternate requests to /new/ and /accounts/find/
        request_count = 0

        def alternate_requests() -> "TestHttpResponse":
            nonlocal request_count
            request_count += 1
            if request_count % 2 == 1:
                return self.submit_realm_creation_form(
                    email="new@zulip.com", realm_subdomain="custom-test", realm_name="Zulip test"
                )
            else:
                return self.client_post("/accounts/find/", {"emails": "new@zulip.com"})

        self.do_test_hit_ratelimits(alternate_requests, is_json=False)

    @contextmanager
    def tor_mock(
        self,
        side_effect: Optional[Exception] = None,
        read_data: Sequence[str] = ["1.2.3.4", "5.6.7.8"],
    ) -> Iterator[mock.Mock]:
        # We need to reset the circuitbreaker before starting.  We
        # patch the .opened property to be false, then call the
        # function, so it resets to closed.
        with mock.patch("builtins.open", mock.mock_open(read_data=orjson.dumps(["1.2.3.4"]))):
            with mock.patch(
                "circuitbreaker.CircuitBreaker.opened", new_callable=mock.PropertyMock
            ) as mock_opened:
                mock_opened.return_value = False
                get_tor_ips()

        # Having closed it, it's now cached.  Clear the cache.
        assert CircuitBreakerMonitor.get("get_tor_ips").closed
        cache_delete("tor_ip_addresses:")

        builtin_open = open
        if side_effect:
            tor_open = mock.MagicMock(side_effect=side_effect)
        else:
            tor_open = mock.mock_open(read_data=orjson.dumps(read_data))

        def selective_mock_open(*args: Any, **kwargs: Any) -> IO[Any]:
            if args[0] == settings.TOR_EXIT_NODE_FILE_PATH:
                return tor_open(*args, **kwargs)
            return builtin_open(*args, **kwargs)

        with mock.patch("builtins.open", selective_mock_open):
            yield tor_open

    @ratelimit_rule(1, 5, domain="api_by_ip")
    @override_settings(RATE_LIMIT_TOR_TOGETHER=True)
    def test_tor_ip_limits(self) -> None:
        request_count = 0
        for ip in ["1.2.3.4", "5.6.7.8", "tor-exit-node"]:
            RateLimitedIPAddr(ip, domain="api_by_ip").clear_history()

        def alternate_requests() -> "TestHttpResponse":
            nonlocal request_count
            request_count += 1
            if request_count % 2 == 1:
                return self.send_unauthed_api_request(REMOTE_ADDR="1.2.3.4")
            else:
                return self.send_unauthed_api_request(REMOTE_ADDR="5.6.7.8")

        with self.tor_mock(read_data=["1.2.3.4", "5.6.7.8"]) as tor_open:
            self.do_test_hit_ratelimits(alternate_requests)

        # This is only read once, despite being used on each request
        tor_open.assert_called_once_with(settings.TOR_EXIT_NODE_FILE_PATH, "rb")
        tor_open().read.assert_called_once()

    @ratelimit_rule(1, 5, domain="api_by_ip")
    @override_settings(RATE_LIMIT_TOR_TOGETHER=True)
    def test_tor_file_empty(self) -> None:
        for ip in ["1.2.3.4", "5.6.7.8", "tor-exit-node"]:
            RateLimitedIPAddr(ip, domain="api_by_ip").clear_history()

        # An empty list of IPs is treated as some error in parsing the
        # input, and as such should not be cached; rate-limiting
        # should work as normal, per-IP
        with self.tor_mock(read_data=[]) as tor_open:
            with self.assertLogs("zerver.lib.rate_limiter", level="WARNING"):
                self.do_test_hit_ratelimits(
                    lambda: self.send_unauthed_api_request(REMOTE_ADDR="1.2.3.4")
                )
                resp = self.send_unauthed_api_request(REMOTE_ADDR="5.6.7.8")
                self.assertNotEqual(resp.status_code, 429)

        # Was not cached, so tried to read twice before hitting the
        # circuit-breaker, and stopping trying
        tor_open().read.assert_has_calls([mock.call(), mock.call()])

    @ratelimit_rule(1, 5, domain="api_by_ip")
    @override_settings(RATE_LIMIT_TOR_TOGETHER=True)
    def test_tor_file_not_found(self) -> None:
        for ip in ["1.2.3.4", "5.6.7.8", "tor-exit-node"]:
            RateLimitedIPAddr(ip, domain="api_by_ip").clear_history()

        with self.tor_mock(side_effect=FileNotFoundError("File not found")) as tor_open:
            # If we cannot get a list of TOR exit nodes, then
            # rate-limiting works as normal, per-IP
            with self.assertLogs("zerver.lib.rate_limiter", level="WARNING") as log_mock:
                self.do_test_hit_ratelimits(
                    lambda: self.send_unauthed_api_request(REMOTE_ADDR="1.2.3.4")
                )
                resp = self.send_unauthed_api_request(REMOTE_ADDR="5.6.7.8")
                self.assertNotEqual(resp.status_code, 429)

        # Tries twice before hitting the circuit-breaker, and stopping trying
        tor_open.assert_has_calls(
            [
                mock.call(settings.TOR_EXIT_NODE_FILE_PATH, "rb"),
                mock.call(settings.TOR_EXIT_NODE_FILE_PATH, "rb"),
            ]
        )

        self.assert_length(log_mock.output, 8)
        self.assertEqual(
            log_mock.output[0:2],
            [
                "WARNING:zerver.lib.rate_limiter:Failed to fetch TOR exit node list: {}".format(
                    "File not found"
                )
            ]
            * 2,
        )
        self.assertIn(
            'Failed to fetch TOR exit node list: Circuit "get_tor_ips" OPEN',
            log_mock.output[3],
        )

    @skipUnless(settings.ZILENCER_ENABLED, "requires zilencer")
    @ratelimit_rule(1, 5, domain="api_by_remote_server")
    def test_hit_ratelimits_as_remote_server(self) -> None:
        server_uuid = str(uuid.uuid4())
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
            with self.assertLogs("zilencer.auth", level="WARNING") as m:
                self.do_test_hit_ratelimits(lambda: self.uuid_post(server_uuid, endpoint, payload))
            self.assertEqual(
                m.output,
                [
                    f"WARNING:zilencer.auth:Remote server demo.example.com {server_uuid[:12]} exceeded rate limits on domain api_by_remote_server"
                ],
            )
        finally:
            self.DEFAULT_SUBDOMAIN = original_default_subdomain

    def test_hit_ratelimiterlockingexception(self) -> None:
        user = self.example_user("cordelia")
        RateLimitedUser(user).clear_history()

        with mock.patch(
            "zerver.lib.rate_limiter.RedisRateLimiterBackend.incr_ratelimit",
            side_effect=RateLimiterLockingError,
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

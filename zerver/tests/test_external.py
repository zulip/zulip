import time
from unittest import mock

import DNS
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpResponse

from zerver.forms import email_is_not_mit_mailing_list
from zerver.lib.rate_limiter import (
    RateLimitedUser,
    RateLimiterLockingException,
    add_ratelimit_rule,
    remove_ratelimit_rule,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.zephyr import compute_mit_user_fullname
from zerver.models import UserProfile


class MITNameTest(ZulipTestCase):
    def test_valid_hesiod(self) -> None:
        with mock.patch('DNS.dnslookup', return_value=[['starnine:*:84233:101:Athena Consulting Exchange User,,,:/mit/starnine:/bin/bash']]):
            self.assertEqual(compute_mit_user_fullname(self.mit_email("starnine")), "Athena Consulting Exchange User")
        with mock.patch('DNS.dnslookup', return_value=[['sipbexch:*:87824:101:Exch Sipb,,,:/mit/sipbexch:/bin/athena/bash']]):
            self.assertEqual(compute_mit_user_fullname("sipbexch@mit.edu"), "Exch Sipb")

    def test_invalid_hesiod(self) -> None:
        with mock.patch('DNS.dnslookup', side_effect=DNS.Base.ServerError('DNS query status: NXDOMAIN', 3)):
            self.assertEqual(compute_mit_user_fullname("1234567890@mit.edu"), "1234567890@mit.edu")
        with mock.patch('DNS.dnslookup', side_effect=DNS.Base.ServerError('DNS query status: NXDOMAIN', 3)):
            self.assertEqual(compute_mit_user_fullname("ec-discuss@mit.edu"), "ec-discuss@mit.edu")

    def test_mailinglist(self) -> None:
        with mock.patch('DNS.dnslookup', side_effect=DNS.Base.ServerError('DNS query status: NXDOMAIN', 3)):
            self.assertRaises(ValidationError, email_is_not_mit_mailing_list, "1234567890@mit.edu")
        with mock.patch('DNS.dnslookup', side_effect=DNS.Base.ServerError('DNS query status: NXDOMAIN', 3)):
            self.assertRaises(ValidationError, email_is_not_mit_mailing_list, "ec-discuss@mit.edu")

    def test_notmailinglist(self) -> None:
        with mock.patch('DNS.dnslookup', return_value=[['POP IMAP.EXCHANGE.MIT.EDU starnine']]):
            email_is_not_mit_mailing_list("sipbexch@mit.edu")

class RateLimitTests(ZulipTestCase):

    def setUp(self) -> None:
        super().setUp()

        # Some tests here can be somewhat timing-sensitive in a way
        # that can't be eliminated, e.g. due to testing things that rely
        # on redis' internal timing mechanism which we can't mock.
        # The first API request when running a suite of tests is slow
        # and can take multiple seconds. This is not a problem when running
        # multiple tests, but if an individual, time-sensitive test from this class
        # is run, the first API request it makes taking a lot of time can throw things off
        # and cause the test to fail. Thus we do a dummy API request here to warm up
        # the system and allow the tests to assume their requests won't take multiple seconds.
        user = self.example_user('hamlet')
        self.api_get(user, "/api/v1/messages")

        settings.RATE_LIMITING = True
        add_ratelimit_rule(1, 5)

    def tearDown(self) -> None:
        settings.RATE_LIMITING = False
        remove_ratelimit_rule(1, 5)

        super().tearDown()

    def send_api_message(self, user: UserProfile, content: str) -> HttpResponse:
        return self.api_post(user, "/api/v1/messages", {"type": "stream",
                                                        "to": "Verona",
                                                        "client": "test suite",
                                                        "content": content,
                                                        "topic": "whatever"})

    def test_headers(self) -> None:
        user = self.example_user('hamlet')
        RateLimitedUser(user).clear_history()

        result = self.send_api_message(user, "some stuff")
        self.assertTrue('X-RateLimit-Remaining' in result)
        self.assertTrue('X-RateLimit-Limit' in result)
        self.assertTrue('X-RateLimit-Reset' in result)

    def test_ratelimit_decrease(self) -> None:
        user = self.example_user('hamlet')
        RateLimitedUser(user).clear_history()
        result = self.send_api_message(user, "some stuff")
        limit = int(result['X-RateLimit-Remaining'])

        result = self.send_api_message(user, "some stuff 2")
        newlimit = int(result['X-RateLimit-Remaining'])
        self.assertEqual(limit, newlimit + 1)

    def test_hit_ratelimits(self) -> None:
        user = self.example_user('cordelia')
        RateLimitedUser(user).clear_history()

        start_time = time.time()
        for i in range(6):
            with mock.patch('time.time', return_value=(start_time + i * 0.1)):
                result = self.send_api_message(user, f"some stuff {i}")

        self.assertEqual(result.status_code, 429)
        json = result.json()
        self.assertEqual(json.get("result"), "error")
        self.assertIn("API usage exceeded rate limit", json.get("msg"))
        self.assertEqual(json.get('retry-after'), 0.5)
        self.assertTrue('Retry-After' in result)
        self.assertEqual(result['Retry-After'], '0.5')

        # We actually wait a second here, rather than force-clearing our history,
        # to make sure the rate-limiting code automatically forgives a user
        # after some time has passed.
        with mock.patch('time.time', return_value=(start_time + 1.01)):
            result = self.send_api_message(user, "Good message")

            self.assert_json_success(result)

    @mock.patch('zerver.lib.rate_limiter.logger.warning')
    def test_hit_ratelimiterlockingexception(self, mock_warn: mock.MagicMock) -> None:
        user = self.example_user('cordelia')
        RateLimitedUser(user).clear_history()

        with mock.patch('zerver.lib.rate_limiter.RedisRateLimiterBackend.incr_ratelimit',
                        side_effect=RateLimiterLockingException):
            result = self.send_api_message(user, "some stuff")
            self.assertEqual(result.status_code, 429)
            mock_warn.assert_called_with(
                "Deadlock trying to incr_ratelimit for %s",
                f"RateLimitedUser:{user.id}:api_by_user",
            )

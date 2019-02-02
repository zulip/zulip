# -*- coding: utf-8 -*-
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpResponse

from zerver.forms import email_is_not_mit_mailing_list

from zerver.lib.rate_limiter import (
    add_ratelimit_rule,
    clear_history,
    remove_ratelimit_rule,
    RateLimitedUser,
)
from zerver.lib.zephyr import compute_mit_user_fullname

from zerver.lib.test_classes import (
    ZulipTestCase,
)

import DNS
import mock
import time

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
        settings.RATE_LIMITING = True
        add_ratelimit_rule(1, 5)

    def tearDown(self) -> None:
        settings.RATE_LIMITING = False
        remove_ratelimit_rule(1, 5)

    def send_api_message(self, email: str, content: str) -> HttpResponse:
        return self.api_post(email, "/api/v1/messages", {"type": "stream",
                                                         "to": "Verona",
                                                         "client": "test suite",
                                                         "content": content,
                                                         "topic": "whatever"})

    def test_headers(self) -> None:
        user = self.example_user('hamlet')
        email = user.email
        clear_history(RateLimitedUser(user))

        result = self.send_api_message(email, "some stuff")
        self.assertTrue('X-RateLimit-Remaining' in result)
        self.assertTrue('X-RateLimit-Limit' in result)
        self.assertTrue('X-RateLimit-Reset' in result)

    def test_ratelimit_decrease(self) -> None:
        user = self.example_user('hamlet')
        email = user.email
        clear_history(RateLimitedUser(user))
        result = self.send_api_message(email, "some stuff")
        limit = int(result['X-RateLimit-Remaining'])

        result = self.send_api_message(email, "some stuff 2")
        newlimit = int(result['X-RateLimit-Remaining'])
        self.assertEqual(limit, newlimit + 1)

    def test_hit_ratelimits(self) -> None:
        user = self.example_user('cordelia')
        email = user.email
        clear_history(RateLimitedUser(user))

        start_time = time.time()
        for i in range(6):
            with mock.patch('time.time', return_value=(start_time + i * 0.1)):
                result = self.send_api_message(email, "some stuff %s" % (i,))

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
        with mock.patch('time.time', return_value=(start_time + 1.0)):
            result = self.send_api_message(email, "Good message")

            self.assert_json_success(result)

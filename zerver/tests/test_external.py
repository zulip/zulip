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
    RateLimitedObject,
    RateLimitedIP,
    RateLimitedEmail,
)

from zerver.lib.actions import compute_mit_user_fullname
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.utils import get_ip

import DNS
import mock
import time

import urllib
from typing import Text

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
    header_prefix = ''

    def send_api_message(self, email: Text, content: Text) -> HttpResponse:
        return self.api_post(email, "/api/v1/messages", {"type": "stream",
                                                         "to": "Verona",
                                                         "client": "test suite",
                                                         "content": content,
                                                         "subject": "Test subject"})

    def _test_headers(self, entity, email):
        # type: (RateLimitedObject, Text) -> None
        clear_history(entity)
        result = self.send_api_message(email, "some stuff")
        self.assertTrue('X{}-RateLimit-Remaining'.format(self.header_prefix) in result)
        self.assertTrue('X{}-RateLimit-Limit'.format(self.header_prefix) in result)
        self.assertTrue('X{}-RateLimit-Reset'.format(self.header_prefix) in result)

    def _test_ratelimit_decrease(self, entity, email):
        # type: (RateLimitedObject, Text) -> None
        clear_history(entity)
        result = self.send_api_message(email, "some stuff")
        limit = int(result['X{}-RateLimit-Remaining'.format(self.header_prefix)])

        result = self.send_api_message(email, "some stuff 2")
        newlimit = int(result['X{}-RateLimit-Remaining'.format(self.header_prefix)])
        self.assertEqual(limit, newlimit + 1)

    def _test_hit_ratelimits(self, entity, email):
        # type: (RateLimitedObject, Text) -> None
        clear_history(entity)

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

class RateLimitUserTests(RateLimitTests):

    def setUp(self) -> None:
        settings.RATE_LIMITING = True
        add_ratelimit_rule(1, 5)

    def tearDown(self) -> None:
        settings.RATE_LIMITING = False
        remove_ratelimit_rule(1, 5)

    def test_headers(self) -> None:
        user = self.example_user('hamlet')
        email = user.email
        self._test_headers(RateLimitedUser(user), email)

    def test_ratelimit_decrease(self) -> None:
        user = self.example_user('hamlet')
        email = user.email
        self._test_ratelimit_decrease(RateLimitedUser(user), email)

    def test_hit_ratelimits(self) -> None:
        user = self.example_user('cordelia')
        email = user.email
        self._test_hit_ratelimits(RateLimitedUser(user), email)

class RateLimitIPTests(RateLimitTests):
    header_prefix = '-Ip'

    def setUp(self):
        # type: () -> None
        settings.IP_RATE_LIMITING = True
        add_ratelimit_rule(1, 5)

    def tearDown(self):
        # type: () -> None
        settings.IP_RATE_LIMITING = False
        remove_ratelimit_rule(1, 5)

    def test_headers(self):
        # type: () -> None
        email = self.example_email('hamlet')
        ip = '192.168.1.1'
        with mock.patch('zerver.middleware.get_ip', return_value=ip), \
                mock.patch('zerver.decorator.get_ip', return_value=ip):
            self._test_headers(RateLimitedIP(ip), email)

    def test_ratelimit_decrease(self):
        # type: () -> None
        email = self.example_email('hamlet')
        ip = '192.168.1.1'
        with mock.patch('zerver.middleware.get_ip', return_value=ip), \
                mock.patch('zerver.decorator.get_ip', return_value=ip):
            self._test_ratelimit_decrease(RateLimitedIP(ip), email)

    def test_hit_ratelimits(self):
        # type: () -> None
        email = self.example_email('hamlet')
        ip = '192.168.1.1'
        with mock.patch('zerver.middleware.get_ip', return_value=ip), \
                mock.patch('zerver.decorator.get_ip', return_value=ip):
            self._test_hit_ratelimits(RateLimitedIP(ip), email)

class EmailAuthTests(RateLimitTests):
    header_prefix = '-Email'

    def setUp(self):
        # type: () -> None
        settings.EMAIL_RATE_LIMITING = True
        add_ratelimit_rule(1, 5)
        self.old_auth_backends = settings.AUTHENTICATION_BACKENDS
        settings.AUTHENTICATION_BACKENDS = ('zproject.backends.EmailAuthBackend',)
        self.email = self.example_email('hamlet')

    def tearDown(self):
        # type: () -> None
        settings.EMAIL_RATE_LIMITING = False
        remove_ratelimit_rule(1, 5)
        settings.AUTHENTICATION_BACKENDS = self.old_auth_backends

    def send_api_message(self, email, password):
        # type: (Text, Text) -> HttpResponse
        return self.client_post("/accounts/login/",
                                info={"username": email, "password": password})

    def _test_hit_ratelimits(self, entity, email):
        # type: (RateLimitedObject, Text) -> None
        clear_history(entity)

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
            result = self.send_api_message(email, "password")
            self.assertEqual(result.status_code, 200)

class EmailRateLimitForEmaiAuthTests(EmailAuthTests):
    """
    These tests check password based authentication against email rate limiting.
    """
    header_prefix = '-Email'

    def setUp(self):
        # type: () -> None
        settings.EMAIL_RATE_LIMITING = True
        super(EmailRateLimitForEmaiAuthTests, self).setUp()

    def tearDown(self):
        # type: () -> None
        settings.EMAIL_RATE_LIMITING = False
        super(EmailRateLimitForEmaiAuthTests, self).tearDown()

    def test_headers(self):
        # type: () -> None
        self._test_headers(RateLimitedEmail(self.email), self.email)

    def test_ratelimit_decrease(self):
        # type: () -> None
        self._test_ratelimit_decrease(RateLimitedEmail(self.email), self.email)

    def test_hit_ratelimits(self):
        # type: () -> None
        self._test_hit_ratelimits(RateLimitedEmail(self.email), self.email)

class IPRateLimitForEmailAuthTests(EmailAuthTests):
    """
    These tests check password based authentication against IP rate limiting.
    """
    header_prefix = '-Ip'

    def setUp(self):
        # type: () -> None
        settings.IP_RATE_LIMITING = True
        self.ip = '192.168.1.1'
        super(IPRateLimitForEmailAuthTests, self).setUp()

    def tearDown(self):
        # type: () -> None
        settings.IP_RATE_LIMITING = False
        super(IPRateLimitForEmailAuthTests, self).tearDown()

    def test_get_ip(self):
        # type: () -> None
        request = mock.MagicMock()
        request.META = {'HTTP_X_FORWARDED_FOR': self.ip}
        self.assertEqual(self.ip, get_ip(request))

        request.META = {'REMOTE_ADDR': self.ip}
        self.assertEqual(self.ip, get_ip(request))

        request.META = {}
        self.assertEqual(None, get_ip(request))

    def test_headers(self):
        # type: () -> None
        with mock.patch('zproject.backends.get_ip', return_value=self.ip):
            self._test_headers(RateLimitedIP(self.ip), self.email)

    def test_ratelimit_decrease(self):
        # type: () -> None
        with mock.patch('zproject.backends.get_ip', return_value=self.ip):
            self._test_ratelimit_decrease(RateLimitedIP(self.ip), self.email)

    def test_hit_ratelimits(self):
        # type: () -> None
        with mock.patch('zproject.backends.get_ip', return_value=self.ip):
            self._test_hit_ratelimits(RateLimitedEmail(self.ip), self.email)

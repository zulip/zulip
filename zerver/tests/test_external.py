# -*- coding: utf-8 -*-
from __future__ import absolute_import
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase

from zerver.forms import not_mit_mailing_list

from zerver.lib.rate_limiter import (
    add_ratelimit_rule,
    clear_user_history,
    remove_ratelimit_rule,
)

from zerver.lib.actions import compute_mit_user_fullname
from zerver.lib.test_helpers import AuthedTestCase
from zerver.models import get_user_profile_by_email
from zerver.lib.test_runner import slow

import DNS
import mock
import time
import ujson
from six.moves import urllib

from six.moves import range

class MITNameTest(TestCase):
    def test_valid_hesiod(self):
        with mock.patch('DNS.dnslookup', return_value=[['starnine:*:84233:101:Athena Consulting Exchange User,,,:/mit/starnine:/bin/bash']]):
            self.assertEquals(compute_mit_user_fullname("starnine@mit.edu"), "Athena Consulting Exchange User")
        with mock.patch('DNS.dnslookup', return_value=[['sipbexch:*:87824:101:Exch Sipb,,,:/mit/sipbexch:/bin/athena/bash']]):
            self.assertEquals(compute_mit_user_fullname("sipbexch@mit.edu"), "Exch Sipb")

    def test_invalid_hesiod(self):
        with mock.patch('DNS.dnslookup', side_effect=DNS.Base.ServerError('DNS query status: NXDOMAIN', 3)):
            self.assertEquals(compute_mit_user_fullname("1234567890@mit.edu"), "1234567890@mit.edu")
        with mock.patch('DNS.dnslookup', side_effect=DNS.Base.ServerError('DNS query status: NXDOMAIN', 3)):
            self.assertEquals(compute_mit_user_fullname("ec-discuss@mit.edu"), "ec-discuss@mit.edu")

    def test_mailinglist(self):
        with mock.patch('DNS.dnslookup', side_effect=DNS.Base.ServerError('DNS query status: NXDOMAIN', 3)):
            self.assertRaises(ValidationError, not_mit_mailing_list, "1234567890@mit.edu")
        with mock.patch('DNS.dnslookup', side_effect=DNS.Base.ServerError('DNS query status: NXDOMAIN', 3)):
            self.assertRaises(ValidationError, not_mit_mailing_list, "ec-discuss@mit.edu")
    def test_notmailinglist(self):
        with mock.patch('DNS.dnslookup', return_value=[['POP IMAP.EXCHANGE.MIT.EDU starnine']]):
            self.assertTrue(not_mit_mailing_list("sipbexch@mit.edu"))

class RateLimitTests(AuthedTestCase):

    def setUp(self):
        settings.RATE_LIMITING = True
        add_ratelimit_rule(1, 5)


    def tearDown(self):
        settings.RATE_LIMITING = False
        remove_ratelimit_rule(1, 5)

    def send_api_message(self, email, api_key, content):
        return self.client.post("/api/v1/send_message", {"type": "stream",
                                                                   "to": "Verona",
                                                                   "client": "test suite",
                                                                   "content": content,
                                                                   "subject": "Test subject",
                                                                   "email": email,
                                                                   "api-key": api_key})
    def test_headers(self):
        email = "hamlet@zulip.com"
        user = get_user_profile_by_email(email)
        clear_user_history(user)
        api_key = self.get_api_key(email)

        result = self.send_api_message(email, api_key, "some stuff")
        self.assertTrue('X-RateLimit-Remaining' in result)
        self.assertTrue('X-RateLimit-Limit' in result)
        self.assertTrue('X-RateLimit-Reset' in result)

    def test_ratelimit_decrease(self):
        email = "hamlet@zulip.com"
        user = get_user_profile_by_email(email)
        clear_user_history(user)
        api_key = self.get_api_key(email)
        result = self.send_api_message(email, api_key, "some stuff")
        limit = int(result['X-RateLimit-Remaining'])

        result = self.send_api_message(email, api_key, "some stuff 2")
        newlimit = int(result['X-RateLimit-Remaining'])
        self.assertEqual(limit, newlimit + 1)

    @slow(1.1, 'has to sleep to work')
    def test_hit_ratelimits(self):
        email = "cordelia@zulip.com"
        user = get_user_profile_by_email(email)
        clear_user_history(user)

        api_key = self.get_api_key(email)
        for i in range(6):
            result = self.send_api_message(email, api_key, "some stuff %s" % (i,))

        self.assertEqual(result.status_code, 429)
        json = ujson.loads(result.content)
        self.assertEqual(json.get("result"), "error")
        self.assertIn("API usage exceeded rate limit, try again in", json.get("msg"))
        self.assertTrue('Retry-After' in result)
        self.assertIn(result['Retry-After'], json.get("msg"))

        # We actually wait a second here, rather than force-clearing our history,
        # to make sure the rate-limiting code automatically forgives a user
        # after some time has passed.
        time.sleep(1)

        result = self.send_api_message(email, api_key, "Good message")

        self.assert_json_success(result)

class APNSTokenTests(AuthedTestCase):
    def test_add_token(self):
        email = "cordelia@zulip.com"
        self.login(email)

        result = self.client.post('/json/users/me/apns_device_token', {'token': "test_token"})
        self.assert_json_success(result)

    def test_delete_token(self):
        email = "cordelia@zulip.com"
        self.login(email)

        token = "test_token"
        result = self.client.post('/json/users/me/apns_device_token', {'token': token})
        self.assert_json_success(result)

        result = self.client_delete('/json/users/me/apns_device_token', {'token': token})
        self.assert_json_success(result)

class GCMTokenTests(AuthedTestCase):
    def test_add_token(self):
        email = "cordelia@zulip.com"
        self.login(email)

        result = self.client.post('/json/users/me/apns_device_token', {'token': "test_token"})
        self.assert_json_success(result)

    def test_delete_token(self):
        email = "cordelia@zulip.com"
        self.login(email)

        token = "test_token"
        result = self.client.post('/json/users/me/android_gcm_reg_id', {'token': token})
        self.assert_json_success(result)

        result = self.client.delete('/json/users/me/android_gcm_reg_id', urllib.parse.urlencode({'token': token}))
        self.assert_json_success(result)

    def test_change_user(self):
        token = "test_token"

        self.login("cordelia@zulip.com")
        result = self.client.post('/json/users/me/android_gcm_reg_id', {'token': token})
        self.assert_json_success(result)

        self.login("hamlet@zulip.com")
        result = self.client.post('/json/users/me/android_gcm_reg_id', {'token': token})
        self.assert_json_success(result)

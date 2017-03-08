# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

from django.http import HttpResponse
from django.utils import timezone
from mock import mock

from typing import Any, Dict
from zerver.lib.actions import do_deactivate_user
from zerver.lib.test_helpers import (
    get_user_profile_by_email,
    make_client,
    queries_captured,
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import (
    email_to_domain,
    Client,
    UserActivity,
    UserProfile,
)

import datetime
import ujson

class ActivityTest(ZulipTestCase):
    def test_activity(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        client, _ = Client.objects.get_or_create(name='website')
        query = '/json/users/me/pointer'
        last_visit = timezone.now()
        count = 150
        for user_profile in UserProfile.objects.all():
            UserActivity.objects.get_or_create(
                user_profile=user_profile,
                client=client,
                query=query,
                count=count,
                last_visit=last_visit
            )
        with queries_captured() as queries:
            self.client_get('/activity')

        self.assert_max_length(queries, 13)

class TestClientModel(ZulipTestCase):
    def test_client_stringification(self):
        # type: () -> None
        '''
        This test is designed to cover __unicode__ method for Client.
        '''
        client = make_client('some_client')
        self.assertEqual(str(client), u'<Client: some_client>')

class UserPresenceTests(ZulipTestCase):
    def test_invalid_presence(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        self.login(email)
        result = self.client_post("/json/users/me/presence", {'status': 'foo'})
        self.assert_json_error(result, 'Invalid status: foo')

    def test_set_idle(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        self.login(email)
        client = 'website'

        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertIn('timestamp', json['presences'][email][client])
        self.assertIsInstance(json['presences'][email][client]['timestamp'], int)
        self.assertEqual(list(json['presences'].keys()), ['hamlet@zulip.com'])
        timestamp = json['presences'][email][client]['timestamp']

        email = "othello@zulip.com"
        self.login(email)
        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')
        self.assertEqual(sorted(json['presences'].keys()), ['hamlet@zulip.com', 'othello@zulip.com'])
        newer_timestamp = json['presences'][email][client]['timestamp']
        self.assertGreaterEqual(newer_timestamp, timestamp)

    def test_set_active(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        client = 'website'

        result = self.client_post("/json/users/me/presence", {'status': 'idle'})

        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences']["hamlet@zulip.com"][client]['status'], 'idle')

        email = "othello@zulip.com"
        self.login("othello@zulip.com")
        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')

        result = self.client_post("/json/users/me/presence", {'status': 'active'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'active')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')

    def test_no_mit(self):
        # type: () -> None
        """Zephyr mirror realms such as MIT never get a list of users"""
        self.login("espuser@mit.edu")
        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'], {})

    def test_mirror_presence(self):
        # type: () -> None
        """Zephyr mirror realms find out the status of their mirror bot"""
        email = 'espuser@mit.edu'
        user_profile = get_user_profile_by_email(email)
        self.login(email)

        def post_presence():
            # type: () -> Dict[str, Any]
            result = self.client_post("/json/users/me/presence", {'status': 'idle'})
            self.assert_json_success(result)
            json = ujson.loads(result.content)
            return json

        json = post_presence()
        self.assertEqual(json['zephyr_mirror_active'], False)

        self._simulate_mirror_activity_for_user(user_profile)
        json = post_presence()
        self.assertEqual(json['zephyr_mirror_active'], True)

    def _simulate_mirror_activity_for_user(self, user_profile):
        # type: (UserProfile) -> None
        last_visit = timezone.now()
        client = make_client('zephyr_mirror')

        UserActivity.objects.get_or_create(
            user_profile=user_profile,
            client=client,
            query='get_events_backend',
            count=2,
            last_visit=last_visit
        )

    def test_same_realm(self):
        # type: () -> None
        self.login("espuser@mit.edu")
        self.client_post("/json/users/me/presence", {'status': 'idle'})
        result = self.client_post("/accounts/logout/")

        # Ensure we don't see hamlet@zulip.com information leakage
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences']["hamlet@zulip.com"]["website"]['status'], 'idle')
        # We only want @zulip.com emails
        for email in json['presences'].keys():
            self.assertEqual(email_to_domain(email), 'zulip.com')

class SingleUserPresenceTests(ZulipTestCase):
    def test_single_user_get(self):
        # type: () -> None

        # First, we setup the test with some data
        email = "othello@zulip.com"
        self.login("othello@zulip.com")
        result = self.client_post("/json/users/me/presence", {'status': 'active'})
        result = self.client_post("/json/users/me/presence", {'status': 'active'},
                                  HTTP_USER_AGENT="ZulipDesktop/1.0")
        result = self.client_post("/api/v1/users/me/presence", {'status': 'idle'},
                                  HTTP_USER_AGENT="ZulipAndroid/1.0",
                                  **self.api_auth(email))
        self.assert_json_success(result)

        # Check some error conditions
        result = self.client_get("/json/users/nonexistence@zulip.com/presence")
        self.assert_json_error(result, "No such user")

        result = self.client_get("/json/users/cordelia@zulip.com/presence")
        self.assert_json_error(result, "No presence data for cordelia@zulip.com")

        do_deactivate_user(get_user_profile_by_email("cordelia@zulip.com"))
        result = self.client_get("/json/users/cordelia@zulip.com/presence")
        self.assert_json_error(result, "No such user")

        result = self.client_get("/json/users/new-user-bot@zulip.com/presence")
        self.assert_json_error(result, "No presence for bot users")

        self.login("sipbtest@mit.edu")
        result = self.client_get("/json/users/othello@zulip.com/presence")
        self.assert_json_error(result, "No such user")

        # Then, we check everything works
        self.login("hamlet@zulip.com")
        result = self.client_get("/json/users/othello@zulip.com/presence")
        result_dict = ujson.loads(result.content)
        self.assertEqual(
            set(result_dict['presence'].keys()),
            {"ZulipAndroid", "website", "aggregated"})
        self.assertEqual(set(result_dict['presence']['website'].keys()), {"status", "timestamp"})


class UserPresenceAggregationTests(ZulipTestCase):
    def _send_presence_for_aggregated_tests(self, email, status, validate_time):
        # type: (str, str, datetime.datetime) -> Dict[str, Dict[str, Any]]
        self.login(email)
        timezone_util = 'django.utils.timezone.now'
        with mock.patch(timezone_util, return_value=validate_time - datetime.timedelta(seconds=5)):
            self.client_post("/json/users/me/presence", {'status': status})
        with mock.patch(timezone_util, return_value=validate_time - datetime.timedelta(seconds=2)):
            self.client_post("/api/v1/users/me/presence", {'status': status},
                             HTTP_USER_AGENT="ZulipAndroid/1.0",
                             **self.api_auth(email))
        with mock.patch(timezone_util, return_value=validate_time - datetime.timedelta(seconds=7)):
            self.client_post("/api/v1/users/me/presence", {'status': status},
                             HTTP_USER_AGENT="ZulipIOS/1.0",
                             **self.api_auth(email))
        result = self.client_get("/json/users/%s/presence" % (email,))
        return result.json()

    def test_aggregated_presense_active(self):
        # type: () -> None
        validate_time = timezone.now()
        result_dict = self._send_presence_for_aggregated_tests('othello@zulip.com', 'active',
                                                               validate_time)
        self.assertDictEqual(
            result_dict['presence']['aggregated'],
            {
                "status": "active",
                "timestamp": datetime_to_timestamp(validate_time - datetime.timedelta(seconds=2))
            }
        )

    def test_aggregated_presense_idle(self):
        # type: () -> None
        validate_time = timezone.now()
        result_dict = self._send_presence_for_aggregated_tests('othello@zulip.com', 'idle',
                                                               validate_time)
        self.assertDictEqual(
            result_dict['presence']['aggregated'],
            {
                "status": "idle",
                "timestamp": datetime_to_timestamp(validate_time - datetime.timedelta(seconds=2))
            }
        )

    def test_aggregated_presense_mixed(self):
        # type: () -> None
        email = "othello@zulip.com"
        self.login(email)
        validate_time = timezone.now()
        with mock.patch('django.utils.timezone.now',
                        return_value=validate_time - datetime.timedelta(seconds=3)):
            self.client_post("/api/v1/users/me/presence", {'status': 'active'},
                             HTTP_USER_AGENT="ZulipTestDev/1.0",
                             **self.api_auth(email))
        result_dict = self._send_presence_for_aggregated_tests(email, 'idle', validate_time)
        self.assertDictEqual(
            result_dict['presence']['aggregated'],
            {
                "status": "idle",
                "timestamp": datetime_to_timestamp(validate_time - datetime.timedelta(seconds=2))
            }
        )

    def test_aggregated_presense_offline(self):
        # type: () -> None
        email = "othello@zulip.com"
        self.login(email)
        validate_time = timezone.now()
        with self.settings(OFFLINE_THRESHOLD_SECS=1):
            result_dict = self._send_presence_for_aggregated_tests(email, 'idle', validate_time)
        self.assertDictEqual(
            result_dict['presence']['aggregated'],
            {
                "status": "offline",
                "timestamp": datetime_to_timestamp(validate_time - datetime.timedelta(seconds=2))
            }
        )

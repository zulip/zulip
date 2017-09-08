# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

from django.http import HttpResponse
from django.utils.timezone import now as timezone_now
from mock import mock

from typing import Any, Dict
from zerver.lib.actions import do_deactivate_user
from zerver.lib.test_helpers import (
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
    PushDeviceToken,
    UserActivity,
    UserProfile,
    UserPresence,
    flush_per_request_caches,
)

import datetime

class ActivityTest(ZulipTestCase):
    def test_activity(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        client, _ = Client.objects.get_or_create(name='website')
        query = '/json/users/me/pointer'
        last_visit = timezone_now()
        count = 150
        for user_profile in UserProfile.objects.all():
            UserActivity.objects.get_or_create(
                user_profile=user_profile,
                client=client,
                query=query,
                count=count,
                last_visit=last_visit
            )
        flush_per_request_caches()
        with queries_captured() as queries:
            self.client_get('/activity')

        self.assert_length(queries, 2)

class TestClientModel(ZulipTestCase):
    def test_client_stringification(self):
        # type: () -> None
        '''
        This test is designed to cover __unicode__ method for Client.
        '''
        client = make_client('some_client')
        self.assertEqual(str(client), u'<Client: some_client>')

class UserPresenceModelTests(ZulipTestCase):
    def test_date_logic(self):
        # type: () -> None
        UserPresence.objects.all().delete()

        user_profile = self.example_user('hamlet')
        email = user_profile.email
        presence_dct = UserPresence.get_status_dict_by_realm(user_profile.realm_id)
        self.assertEqual(len(presence_dct), 0)

        self.login(email)
        result = self.client_post("/json/users/me/presence", {'status': 'active'})
        self.assert_json_success(result)

        presence_dct = UserPresence.get_status_dict_by_realm(user_profile.realm_id)
        self.assertEqual(len(presence_dct), 1)
        self.assertEqual(presence_dct[email]['website']['status'], 'active')

        def back_date(num_weeks):
            # type: (int) -> None
            user_presence = UserPresence.objects.filter(user_profile=user_profile)[0]
            user_presence.timestamp = timezone_now() - datetime.timedelta(weeks=num_weeks)
            user_presence.save()

        # Simulate the presence being a week old first.  Nothing should change.
        back_date(num_weeks=1)
        presence_dct = UserPresence.get_status_dict_by_realm(user_profile.realm_id)
        self.assertEqual(len(presence_dct), 1)

        # If the UserPresence row is three weeks old, we ignore it.
        back_date(num_weeks=3)
        presence_dct = UserPresence.get_status_dict_by_realm(user_profile.realm_id)
        self.assertEqual(len(presence_dct), 0)

    def test_push_tokens(self):
        # type: () -> None
        UserPresence.objects.all().delete()

        user_profile = self.example_user('hamlet')
        email = user_profile.email

        self.login(email)
        result = self.client_post("/json/users/me/presence", {'status': 'active'})
        self.assert_json_success(result)

        def pushable():
            # type: () -> bool
            presence_dct = UserPresence.get_status_dict_by_realm(user_profile.realm_id)
            self.assertEqual(len(presence_dct), 1)
            return presence_dct[email]['website']['pushable']

        self.assertFalse(pushable())

        user_profile.enable_offline_push_notifications = True
        user_profile.save()

        self.assertFalse(pushable())

        PushDeviceToken.objects.create(
            user=user_profile,
            kind=PushDeviceToken.APNS
        )
        self.assertTrue(pushable())

class UserPresenceTests(ZulipTestCase):
    def test_invalid_presence(self):
        # type: () -> None
        email = self.example_email("hamlet")
        self.login(email)
        result = self.client_post("/json/users/me/presence", {'status': 'foo'})
        self.assert_json_error(result, 'Invalid status: foo')

    def test_set_idle(self):
        # type: () -> None
        email = self.example_email("hamlet")
        self.login(email)
        client = 'website'

        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        self.assert_json_success(result)
        json = result.json()
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertIn('timestamp', json['presences'][email][client])
        self.assertIsInstance(json['presences'][email][client]['timestamp'], int)
        self.assertEqual(list(json['presences'].keys()), [self.example_email("hamlet")])
        timestamp = json['presences'][email][client]['timestamp']

        email = self.example_email("othello")
        self.login(email)
        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        json = result.json()
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertEqual(json['presences'][self.example_email("hamlet")][client]['status'], 'idle')
        self.assertEqual(sorted(json['presences'].keys()), [self.example_email("hamlet"), self.example_email("othello")])
        newer_timestamp = json['presences'][email][client]['timestamp']
        self.assertGreaterEqual(newer_timestamp, timestamp)

    def test_set_active(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        client = 'website'

        result = self.client_post("/json/users/me/presence", {'status': 'idle'})

        self.assert_json_success(result)
        self.assertEqual(result.json()['presences'][self.example_email("hamlet")][client]['status'], 'idle')

        email = self.example_email("othello")
        self.login(self.example_email("othello"))
        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        self.assert_json_success(result)
        json = result.json()
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertEqual(json['presences'][self.example_email("hamlet")][client]['status'], 'idle')

        result = self.client_post("/json/users/me/presence", {'status': 'active'})
        self.assert_json_success(result)
        json = result.json()
        self.assertEqual(json['presences'][email][client]['status'], 'active')
        self.assertEqual(json['presences'][self.example_email("hamlet")][client]['status'], 'idle')

    def test_no_mit(self):
        # type: () -> None
        """Zephyr mirror realms such as MIT never get a list of users"""
        self.login(self.mit_email("espuser"))
        result = self.client_post("/json/users/me/presence", {'status': 'idle'},
                                  subdomain="zephyr")
        self.assert_json_success(result)
        self.assertEqual(result.json()['presences'], {})

    def test_mirror_presence(self):
        # type: () -> None
        """Zephyr mirror realms find out the status of their mirror bot"""
        user_profile = self.mit_user('espuser')
        email = user_profile.email
        self.login(email)

        def post_presence():
            # type: () -> Dict[str, Any]
            result = self.client_post("/json/users/me/presence", {'status': 'idle'},
                                      subdomain="zephyr")
            self.assert_json_success(result)
            json = result.json()
            return json

        json = post_presence()
        self.assertEqual(json['zephyr_mirror_active'], False)

        self._simulate_mirror_activity_for_user(user_profile)
        json = post_presence()
        self.assertEqual(json['zephyr_mirror_active'], True)

    def _simulate_mirror_activity_for_user(self, user_profile):
        # type: (UserProfile) -> None
        last_visit = timezone_now()
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
        self.login(self.mit_email("espuser"))
        self.client_post("/json/users/me/presence", {'status': 'idle'},
                         subdomain="zephyr")
        self.logout()

        # Ensure we don't see hamlet@zulip.com information leakage
        self.login(self.example_email("hamlet"))
        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        self.assert_json_success(result)
        json = result.json()
        self.assertEqual(json['presences'][self.example_email("hamlet")]["website"]['status'], 'idle')
        # We only want @zulip.com emails
        for email in json['presences'].keys():
            self.assertEqual(email_to_domain(email), 'zulip.com')

class SingleUserPresenceTests(ZulipTestCase):
    def test_single_user_get(self):
        # type: () -> None

        # First, we setup the test with some data
        email = self.example_email("othello")
        self.login(self.example_email("othello"))
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

        do_deactivate_user(self.example_user('cordelia'))
        result = self.client_get("/json/users/cordelia@zulip.com/presence")
        self.assert_json_error(result, "No such user")

        result = self.client_get("/json/users/new-user-bot@zulip.com/presence")
        self.assert_json_error(result, "Presence is not supported for bot users.")

        self.login(self.mit_email("sipbtest"))
        result = self.client_get("/json/users/othello@zulip.com/presence",
                                 subdomain="zephyr")
        self.assert_json_error(result, "No such user")

        # Then, we check everything works
        self.login(self.example_email("hamlet"))
        result = self.client_get("/json/users/othello@zulip.com/presence")
        result_dict = result.json()
        self.assertEqual(
            set(result_dict['presence'].keys()),
            {"ZulipAndroid", "website", "aggregated"})
        self.assertEqual(set(result_dict['presence']['website'].keys()), {"status", "timestamp"})

    def test_ping_only(self):
        # type: () -> None

        self.login(self.example_email("othello"))
        req = dict(
            status='active',
            ping_only='true',
        )
        result = self.client_post("/json/users/me/presence", req)
        self.assertEqual(result.json()['msg'], '')

class UserPresenceAggregationTests(ZulipTestCase):
    def _send_presence_for_aggregated_tests(self, email, status, validate_time):
        # type: (str, str, datetime.datetime) -> Dict[str, Dict[str, Any]]
        self.login(email)
        timezone_util = 'zerver.views.presence.timezone_now'
        with mock.patch(timezone_util, return_value=validate_time - datetime.timedelta(seconds=5)):
            self.client_post("/json/users/me/presence", {'status': status})
        with mock.patch(timezone_util, return_value=validate_time - datetime.timedelta(seconds=2)):
            self.client_post("/api/v1/users/me/presence", {'status': status},
                             HTTP_USER_AGENT="ZulipAndroid/1.0",
                             **self.api_auth(email))
        with mock.patch(timezone_util, return_value=validate_time - datetime.timedelta(seconds=7)):
            latest_result = self.client_post("/api/v1/users/me/presence", {'status': status},
                                             HTTP_USER_AGENT="ZulipIOS/1.0",
                                             **self.api_auth(email))
        latest_result_dict = latest_result.json()
        self.assertDictEqual(
            latest_result_dict['presences'][email]['aggregated'],
            {
                'status': status,
                'timestamp': datetime_to_timestamp(validate_time - datetime.timedelta(seconds=2)),
                'client': 'ZulipAndroid'
            }
        )
        result = self.client_get("/json/users/%s/presence" % (email,))
        return result.json()

    def test_aggregated_info(self):
        # type: () -> None
        email = self.example_email("othello")
        validate_time = timezone_now()
        self._send_presence_for_aggregated_tests(str(self.example_email("othello")), 'active', validate_time)
        with mock.patch('zerver.views.presence.timezone_now',
                        return_value=validate_time - datetime.timedelta(seconds=1)):
            result = self.client_post("/api/v1/users/me/presence", {'status': 'active'},
                                      HTTP_USER_AGENT="ZulipTestDev/1.0",
                                      **self.api_auth(email))
        result_dict = result.json()
        self.assertDictEqual(
            result_dict['presences'][email]['aggregated'],
            {
                'status': 'active',
                'timestamp': datetime_to_timestamp(validate_time - datetime.timedelta(seconds=1)),
                'client': 'ZulipTestDev'
            }
        )

    def test_aggregated_presense_active(self):
        # type: () -> None
        validate_time = timezone_now()
        result_dict = self._send_presence_for_aggregated_tests(str(self.example_email("othello")), 'active',
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
        validate_time = timezone_now()
        result_dict = self._send_presence_for_aggregated_tests(str(self.example_email("othello")), 'idle',
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
        email = self.example_email("othello")
        self.login(email)
        validate_time = timezone_now()
        with mock.patch('zerver.views.presence.timezone_now',
                        return_value=validate_time - datetime.timedelta(seconds=3)):
            self.client_post("/api/v1/users/me/presence", {'status': 'active'},
                             HTTP_USER_AGENT="ZulipTestDev/1.0",
                             **self.api_auth(email))
        result_dict = self._send_presence_for_aggregated_tests(str(email), 'idle', validate_time)
        self.assertDictEqual(
            result_dict['presence']['aggregated'],
            {
                "status": "idle",
                "timestamp": datetime_to_timestamp(validate_time - datetime.timedelta(seconds=2))
            }
        )

    def test_aggregated_presense_offline(self):
        # type: () -> None
        email = self.example_email("othello")
        self.login(email)
        validate_time = timezone_now()
        with self.settings(OFFLINE_THRESHOLD_SECS=1):
            result_dict = self._send_presence_for_aggregated_tests(str(email), 'idle', validate_time)
        self.assertDictEqual(
            result_dict['presence']['aggregated'],
            {
                "status": "offline",
                "timestamp": datetime_to_timestamp(validate_time - datetime.timedelta(seconds=2))
            }
        )

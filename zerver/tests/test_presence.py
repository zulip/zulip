# -*- coding: utf-8 -*-

from datetime import timedelta
from django.utils.timezone import now as timezone_now
import mock

from typing import Any, Dict
from zerver.lib.actions import do_deactivate_user
from zerver.lib.statistics import seconds_usage_between
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
    UserActivityInterval,
    UserProfile,
    UserPresence,
    flush_per_request_caches,
    get_realm,
)

import datetime

class ActivityTest(ZulipTestCase):
    @mock.patch("stripe.Customer.list", return_value=[])
    def test_activity(self, unused_mock: mock.Mock) -> None:
        self.login(self.example_email("hamlet"))
        client, _ = Client.objects.get_or_create(name='website')
        query = '/json/users/me/pointer'
        last_visit = timezone_now()
        count = 150
        for activity_user_profile in UserProfile.objects.all():
            UserActivity.objects.get_or_create(
                user_profile=activity_user_profile,
                client=client,
                query=query,
                count=count,
                last_visit=last_visit
            )

        # Fails when not staff
        result = self.client_get('/activity')
        self.assertEqual(result.status_code, 302)

        user_profile = self.example_user("hamlet")
        user_profile.is_staff = True
        user_profile.save()

        flush_per_request_caches()
        with queries_captured() as queries:
            result = self.client_get('/activity')
            self.assertEqual(result.status_code, 200)

        self.assert_length(queries, 15)

        flush_per_request_caches()
        with queries_captured() as queries:
            result = self.client_get('/realm_activity/zulip/')
            self.assertEqual(result.status_code, 200)

        self.assert_length(queries, 9)

        flush_per_request_caches()
        with queries_captured() as queries:
            result = self.client_get('/user_activity/iago@zulip.com/')
            self.assertEqual(result.status_code, 200)

        self.assert_length(queries, 5)

class TestClientModel(ZulipTestCase):
    def test_client_stringification(self) -> None:
        '''
        This test is designed to cover __str__ method for Client.
        '''
        client = make_client('some_client')
        self.assertEqual(str(client), '<Client: some_client>')

class UserPresenceModelTests(ZulipTestCase):
    def test_date_logic(self) -> None:
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

        def back_date(num_weeks: int) -> None:
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

    def test_push_tokens(self) -> None:
        UserPresence.objects.all().delete()

        user_profile = self.example_user('hamlet')
        email = user_profile.email

        self.login(email)
        result = self.client_post("/json/users/me/presence", {'status': 'active'})
        self.assert_json_success(result)

        def pushable() -> bool:
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
    def test_invalid_presence(self) -> None:
        email = self.example_email("hamlet")
        self.login(email)
        result = self.client_post("/json/users/me/presence", {'status': 'foo'})
        self.assert_json_error(result, 'Invalid status: foo')

    def test_set_idle(self) -> None:
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

    def test_set_active(self) -> None:
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

    @mock.patch("stripe.Customer.list", return_value=[])
    def test_new_user_input(self, unused_mock: mock.Mock) -> None:
        """Mostly a test for UserActivityInterval"""
        user_profile = self.example_user("hamlet")
        self.login(self.example_email("hamlet"))
        self.assertEqual(UserActivityInterval.objects.filter(user_profile=user_profile).count(), 0)
        time_zero = timezone_now().replace(microsecond=0)
        with mock.patch('zerver.views.presence.timezone_now', return_value=time_zero):
            result = self.client_post("/json/users/me/presence", {'status': 'active',
                                                                  'new_user_input': 'true'})
        self.assert_json_success(result)
        self.assertEqual(UserActivityInterval.objects.filter(user_profile=user_profile).count(), 1)
        interval = UserActivityInterval.objects.get(user_profile=user_profile)
        self.assertEqual(interval.start, time_zero)
        self.assertEqual(interval.end, time_zero + UserActivityInterval.MIN_INTERVAL_LENGTH)

        second_time = time_zero + timedelta(seconds=600)
        # Extent the interval
        with mock.patch('zerver.views.presence.timezone_now', return_value=second_time):
            result = self.client_post("/json/users/me/presence", {'status': 'active',
                                                                  'new_user_input': 'true'})
        self.assert_json_success(result)
        self.assertEqual(UserActivityInterval.objects.filter(user_profile=user_profile).count(), 1)
        interval = UserActivityInterval.objects.get(user_profile=user_profile)
        self.assertEqual(interval.start, time_zero)
        self.assertEqual(interval.end, second_time + UserActivityInterval.MIN_INTERVAL_LENGTH)

        third_time = time_zero + timedelta(seconds=6000)
        with mock.patch('zerver.views.presence.timezone_now', return_value=third_time):
            result = self.client_post("/json/users/me/presence", {'status': 'active',
                                                                  'new_user_input': 'true'})
        self.assert_json_success(result)
        self.assertEqual(UserActivityInterval.objects.filter(user_profile=user_profile).count(), 2)
        interval = UserActivityInterval.objects.filter(user_profile=user_profile).order_by('start')[0]
        self.assertEqual(interval.start, time_zero)
        self.assertEqual(interval.end, second_time + UserActivityInterval.MIN_INTERVAL_LENGTH)
        interval = UserActivityInterval.objects.filter(user_profile=user_profile).order_by('start')[1]
        self.assertEqual(interval.start, third_time)
        self.assertEqual(interval.end, third_time + UserActivityInterval.MIN_INTERVAL_LENGTH)

        self.assertEqual(
            seconds_usage_between(
                user_profile, time_zero, third_time).total_seconds(),
            1500)
        self.assertEqual(
            seconds_usage_between(
                user_profile, time_zero, third_time+timedelta(seconds=10)).total_seconds(),
            1510)
        self.assertEqual(
            seconds_usage_between(
                user_profile, time_zero, third_time+timedelta(seconds=1000)).total_seconds(),
            2400)
        self.assertEqual(
            seconds_usage_between(
                user_profile, time_zero, third_time - timedelta(seconds=100)).total_seconds(),
            1500)
        self.assertEqual(
            seconds_usage_between(
                user_profile, time_zero + timedelta(seconds=100),
                third_time - timedelta(seconds=100)).total_seconds(),
            1400)
        self.assertEqual(
            seconds_usage_between(
                user_profile, time_zero + timedelta(seconds=1200),
                third_time - timedelta(seconds=100)).total_seconds(),
            300)

        # Now test /activity with actual data
        user_profile.is_staff = True
        user_profile.save()
        result = self.client_get('/activity')
        self.assertEqual(result.status_code, 200)

    def test_filter_presence_idle_user_ids(self) -> None:
        user_profile = self.example_user("hamlet")
        from zerver.lib.actions import filter_presence_idle_user_ids
        self.login(self.example_email("hamlet"))

        self.assertEqual(filter_presence_idle_user_ids({user_profile.id}), [user_profile.id])
        self.client_post("/json/users/me/presence", {'status': 'idle'})
        self.assertEqual(filter_presence_idle_user_ids({user_profile.id}), [user_profile.id])
        self.client_post("/json/users/me/presence", {'status': 'active'})
        self.assertEqual(filter_presence_idle_user_ids({user_profile.id}), [])

    def test_no_mit(self) -> None:
        """Zephyr mirror realms such as MIT never get a list of users"""
        self.login(self.mit_email("espuser"), realm=get_realm("zephyr"))
        result = self.client_post("/json/users/me/presence", {'status': 'idle'},
                                  subdomain="zephyr")
        self.assert_json_success(result)
        self.assertEqual(result.json()['presences'], {})

    def test_mirror_presence(self) -> None:
        """Zephyr mirror realms find out the status of their mirror bot"""
        user_profile = self.mit_user('espuser')
        email = user_profile.email
        self.login(email, realm=user_profile.realm)

        def post_presence() -> Dict[str, Any]:
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

    def _simulate_mirror_activity_for_user(self, user_profile: UserProfile) -> None:
        last_visit = timezone_now()
        client = make_client('zephyr_mirror')

        UserActivity.objects.get_or_create(
            user_profile=user_profile,
            client=client,
            query='get_events',
            count=2,
            last_visit=last_visit
        )

    def test_same_realm(self) -> None:
        self.login(self.mit_email("espuser"), realm=get_realm("zephyr"))
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
    def test_single_user_get(self) -> None:

        # First, we setup the test with some data
        email = self.example_email("othello")
        self.login(self.example_email("othello"))
        result = self.client_post("/json/users/me/presence", {'status': 'active'})
        result = self.client_post("/json/users/me/presence", {'status': 'active'},
                                  HTTP_USER_AGENT="ZulipDesktop/1.0")
        result = self.api_post(email, "/api/v1/users/me/presence", {'status': 'idle'},
                               HTTP_USER_AGENT="ZulipAndroid/1.0")
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

        self.login(self.mit_email("sipbtest"), realm=get_realm("zephyr"))
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

    def test_ping_only(self) -> None:

        self.login(self.example_email("othello"))
        req = dict(
            status='active',
            ping_only='true',
        )
        result = self.client_post("/json/users/me/presence", req)
        self.assertEqual(result.json()['msg'], '')

class UserPresenceAggregationTests(ZulipTestCase):
    def _send_presence_for_aggregated_tests(self, email: str, status: str,
                                            validate_time: datetime.datetime) -> Dict[str, Dict[str, Any]]:
        self.login(email)
        timezone_util = 'zerver.views.presence.timezone_now'
        with mock.patch(timezone_util, return_value=validate_time - datetime.timedelta(seconds=5)):
            self.client_post("/json/users/me/presence", {'status': status})
        with mock.patch(timezone_util, return_value=validate_time - datetime.timedelta(seconds=2)):
            self.api_post(email, "/api/v1/users/me/presence", {'status': status},
                          HTTP_USER_AGENT="ZulipAndroid/1.0")
        with mock.patch(timezone_util, return_value=validate_time - datetime.timedelta(seconds=7)):
            latest_result = self.api_post(email, "/api/v1/users/me/presence", {'status': status},
                                          HTTP_USER_AGENT="ZulipIOS/1.0")
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

    def test_aggregated_info(self) -> None:
        email = self.example_email("othello")
        validate_time = timezone_now()
        self._send_presence_for_aggregated_tests(str(self.example_email("othello")), 'active', validate_time)
        with mock.patch('zerver.views.presence.timezone_now',
                        return_value=validate_time - datetime.timedelta(seconds=1)):
            result = self.api_post(email, "/api/v1/users/me/presence", {'status': 'active'},
                                   HTTP_USER_AGENT="ZulipTestDev/1.0")
        result_dict = result.json()
        self.assertDictEqual(
            result_dict['presences'][email]['aggregated'],
            {
                'status': 'active',
                'timestamp': datetime_to_timestamp(validate_time - datetime.timedelta(seconds=1)),
                'client': 'ZulipTestDev'
            }
        )

    def test_aggregated_presense_active(self) -> None:
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

    def test_aggregated_presense_idle(self) -> None:
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

    def test_aggregated_presense_mixed(self) -> None:
        email = self.example_email("othello")
        self.login(email)
        validate_time = timezone_now()
        with mock.patch('zerver.views.presence.timezone_now',
                        return_value=validate_time - datetime.timedelta(seconds=3)):
            self.api_post(email, "/api/v1/users/me/presence", {'status': 'active'},
                          HTTP_USER_AGENT="ZulipTestDev/1.0")
        result_dict = self._send_presence_for_aggregated_tests(str(email), 'idle', validate_time)
        self.assertDictEqual(
            result_dict['presence']['aggregated'],
            {
                "status": "idle",
                "timestamp": datetime_to_timestamp(validate_time - datetime.timedelta(seconds=2))
            }
        )

    def test_aggregated_presense_offline(self) -> None:
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

class GetRealmStatusesTest(ZulipTestCase):
    def test_get_statuses(self) -> None:
        # Setup the test by simulating users reporting their presence data.
        othello_email = self.example_email("othello")
        result = self.api_post(othello_email, "/api/v1/users/me/presence", {'status': 'active'},
                               HTTP_USER_AGENT="ZulipAndroid/1.0")

        hamlet_email = self.example_email("hamlet")
        result = self.api_post(hamlet_email, "/api/v1/users/me/presence", {'status': 'idle'},
                               HTTP_USER_AGENT="ZulipDesktop/1.0")
        self.assert_json_success(result)

        # Check that a bot can fetch the presence data for the realm.
        result = self.api_get(self.example_email("welcome_bot"), "/api/v1/realm/presence")
        self.assert_json_success(result)
        json = result.json()
        self.assertEqual(sorted(json['presences'].keys()), [hamlet_email, othello_email])

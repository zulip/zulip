from datetime import datetime, timedelta, timezone
from typing import List, Optional
from unittest import mock

import orjson
from django.http import HttpResponse
from django.utils.timezone import now as timezone_now

from analytics.lib.counts import COUNT_STATS, CountStat
from analytics.lib.time_utils import time_range
from analytics.models import FillState, RealmCount, UserCount, last_successful_fill
from analytics.views import rewrite_client_arrays, sort_by_totals, sort_client_labels
from corporate.lib.stripe import add_months, update_sponsorship_status
from corporate.models import Customer, CustomerPlan, LicenseLedger, get_customer_by_realm
from zerver.lib.actions import do_create_multiuse_invite_link, do_send_realm_reactivation_email
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import reset_emails_in_zulip_realm
from zerver.lib.timestamp import ceiling_to_day, ceiling_to_hour, datetime_to_timestamp
from zerver.models import (
    Client,
    MultiuseInvite,
    PreregistrationUser,
    Realm,
    UserMessage,
    UserProfile,
    get_realm,
)


class TestStatsEndpoint(ZulipTestCase):
    def test_stats(self) -> None:
        self.user = self.example_user('hamlet')
        self.login_user(self.user)
        result = self.client_get('/stats')
        self.assertEqual(result.status_code, 200)
        # Check that we get something back
        self.assert_in_response("Zulip analytics for", result)

    def test_guest_user_cant_access_stats(self) -> None:
        self.user = self.example_user('polonius')
        self.login_user(self.user)
        result = self.client_get('/stats')
        self.assert_json_error(result, "Not allowed for guest users", 400)

        result = self.client_get('/json/analytics/chart_data')
        self.assert_json_error(result, "Not allowed for guest users", 400)

    def test_stats_for_realm(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        result = self.client_get('/stats/realm/zulip/')
        self.assertEqual(result.status_code, 302)

        result = self.client_get('/stats/realm/not_existing_realm/')
        self.assertEqual(result.status_code, 302)

        user = self.example_user('hamlet')
        user.is_staff = True
        user.save(update_fields=['is_staff'])

        result = self.client_get('/stats/realm/not_existing_realm/')
        self.assertEqual(result.status_code, 404)

        result = self.client_get('/stats/realm/zulip/')
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Zulip analytics for", result)

    def test_stats_for_installation(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        result = self.client_get('/stats/installation')
        self.assertEqual(result.status_code, 302)

        user = self.example_user('hamlet')
        user.is_staff = True
        user.save(update_fields=['is_staff'])

        result = self.client_get('/stats/installation')
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Zulip analytics for", result)

class TestGetChartData(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.realm = get_realm('zulip')
        self.user = self.example_user('hamlet')
        self.login_user(self.user)
        self.end_times_hour = [ceiling_to_hour(self.realm.date_created) + timedelta(hours=i)
                               for i in range(4)]
        self.end_times_day = [ceiling_to_day(self.realm.date_created) + timedelta(days=i)
                              for i in range(4)]

    def data(self, i: int) -> List[int]:
        return [0, 0, i, 0]

    def insert_data(self, stat: CountStat, realm_subgroups: List[Optional[str]],
                    user_subgroups: List[str]) -> None:
        if stat.frequency == CountStat.HOUR:
            insert_time = self.end_times_hour[2]
            fill_time = self.end_times_hour[-1]
        if stat.frequency == CountStat.DAY:
            insert_time = self.end_times_day[2]
            fill_time = self.end_times_day[-1]

        RealmCount.objects.bulk_create(
            RealmCount(property=stat.property, subgroup=subgroup, end_time=insert_time,
                       value=100+i, realm=self.realm)
            for i, subgroup in enumerate(realm_subgroups))
        UserCount.objects.bulk_create(
            UserCount(property=stat.property, subgroup=subgroup, end_time=insert_time,
                      value=200+i, realm=self.realm, user=self.user)
            for i, subgroup in enumerate(user_subgroups))
        FillState.objects.create(property=stat.property, end_time=fill_time, state=FillState.DONE)

    def test_number_of_humans(self) -> None:
        stat = COUNT_STATS['realm_active_humans::day']
        self.insert_data(stat, [None], [])
        stat = COUNT_STATS['1day_actives::day']
        self.insert_data(stat, [None], [])
        stat = COUNT_STATS['active_users_audit:is_bot:day']
        self.insert_data(stat, ['false'], [])
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'number_of_humans'})
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data, {
            'msg': '',
            'end_times': [datetime_to_timestamp(dt) for dt in self.end_times_day],
            'frequency': CountStat.DAY,
            'everyone': {'_1day': self.data(100), '_15day': self.data(100), 'all_time': self.data(100)},
            'display_order': None,
            'result': 'success',
        })

    def test_messages_sent_over_time(self) -> None:
        stat = COUNT_STATS['messages_sent:is_bot:hour']
        self.insert_data(stat, ['true', 'false'], ['false'])
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'messages_sent_over_time'})
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data, {
            'msg': '',
            'end_times': [datetime_to_timestamp(dt) for dt in self.end_times_hour],
            'frequency': CountStat.HOUR,
            'everyone': {'bot': self.data(100), 'human': self.data(101)},
            'user': {'bot': self.data(0), 'human': self.data(200)},
            'display_order': None,
            'result': 'success',
        })

    def test_messages_sent_by_message_type(self) -> None:
        stat = COUNT_STATS['messages_sent:message_type:day']
        self.insert_data(stat, ['public_stream', 'private_message'],
                         ['public_stream', 'private_stream'])
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'messages_sent_by_message_type'})
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data, {
            'msg': '',
            'end_times': [datetime_to_timestamp(dt) for dt in self.end_times_day],
            'frequency': CountStat.DAY,
            'everyone': {'Public streams': self.data(100), 'Private streams': self.data(0),
                         'Private messages': self.data(101), 'Group private messages': self.data(0)},
            'user': {'Public streams': self.data(200), 'Private streams': self.data(201),
                     'Private messages': self.data(0), 'Group private messages': self.data(0)},
            'display_order': ['Private messages', 'Public streams', 'Private streams', 'Group private messages'],
            'result': 'success',
        })

    def test_messages_sent_by_client(self) -> None:
        stat = COUNT_STATS['messages_sent:client:day']
        client1 = Client.objects.create(name='client 1')
        client2 = Client.objects.create(name='client 2')
        client3 = Client.objects.create(name='client 3')
        client4 = Client.objects.create(name='client 4')
        self.insert_data(stat, [client4.id, client3.id, client2.id],
                         [client3.id, client1.id])
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'messages_sent_by_client'})
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data, {
            'msg': '',
            'end_times': [datetime_to_timestamp(dt) for dt in self.end_times_day],
            'frequency': CountStat.DAY,
            'everyone': {'client 4': self.data(100), 'client 3': self.data(101),
                         'client 2': self.data(102)},
            'user': {'client 3': self.data(200), 'client 1': self.data(201)},
            'display_order': ['client 1', 'client 2', 'client 3', 'client 4'],
            'result': 'success',
        })

    def test_messages_read_over_time(self) -> None:
        stat = COUNT_STATS['messages_read::hour']
        self.insert_data(stat, [None], [])
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'messages_read_over_time'})
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data, {
            'msg': '',
            'end_times': [datetime_to_timestamp(dt) for dt in self.end_times_hour],
            'frequency': CountStat.HOUR,
            'everyone': {'read': self.data(100)},
            'user': {'read': self.data(0)},
            'display_order': None,
            'result': 'success',
        })

    def test_include_empty_subgroups(self) -> None:
        FillState.objects.create(
            property='realm_active_humans::day', end_time=self.end_times_day[0],
            state=FillState.DONE)
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'number_of_humans'})
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data['everyone'], {"_1day": [0], "_15day": [0], "all_time": [0]})
        self.assertFalse('user' in data)

        FillState.objects.create(
            property='messages_sent:is_bot:hour', end_time=self.end_times_hour[0],
            state=FillState.DONE)
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'messages_sent_over_time'})
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data['everyone'], {'human': [0], 'bot': [0]})
        self.assertEqual(data['user'], {'human': [0], 'bot': [0]})

        FillState.objects.create(
            property='messages_sent:message_type:day', end_time=self.end_times_day[0],
            state=FillState.DONE)
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'messages_sent_by_message_type'})
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data['everyone'], {
            'Public streams': [0], 'Private streams': [0],
            'Private messages': [0], 'Group private messages': [0]})
        self.assertEqual(data['user'], {
            'Public streams': [0], 'Private streams': [0],
            'Private messages': [0], 'Group private messages': [0]})

        FillState.objects.create(
            property='messages_sent:client:day', end_time=self.end_times_day[0],
            state=FillState.DONE)
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'messages_sent_by_client'})
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data['everyone'], {})
        self.assertEqual(data['user'], {})

    def test_start_and_end(self) -> None:
        stat = COUNT_STATS['realm_active_humans::day']
        self.insert_data(stat, [None], [])
        stat = COUNT_STATS['1day_actives::day']
        self.insert_data(stat, [None], [])
        stat = COUNT_STATS['active_users_audit:is_bot:day']
        self.insert_data(stat, ['false'], [])
        end_time_timestamps = [datetime_to_timestamp(dt) for dt in self.end_times_day]

        # valid start and end
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'number_of_humans',
                                  'start': end_time_timestamps[1],
                                  'end': end_time_timestamps[2]})
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data['end_times'], end_time_timestamps[1:3])
        self.assertEqual(data['everyone'], {'_1day': [0, 100], '_15day': [0, 100], 'all_time': [0, 100]})

        # start later then end
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'number_of_humans',
                                  'start': end_time_timestamps[2],
                                  'end': end_time_timestamps[1]})
        self.assert_json_error_contains(result, 'Start time is later than')

    def test_min_length(self) -> None:
        stat = COUNT_STATS['realm_active_humans::day']
        self.insert_data(stat, [None], [])
        stat = COUNT_STATS['1day_actives::day']
        self.insert_data(stat, [None], [])
        stat = COUNT_STATS['active_users_audit:is_bot:day']
        self.insert_data(stat, ['false'], [])
        # test min_length is too short to change anything
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'number_of_humans',
                                  'min_length': 2})
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data['end_times'], [datetime_to_timestamp(dt) for dt in self.end_times_day])
        self.assertEqual(data['everyone'], {'_1day': self.data(100), '_15day': self.data(100), 'all_time': self.data(100)})
        # test min_length larger than filled data
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'number_of_humans',
                                  'min_length': 5})
        self.assert_json_success(result)
        data = result.json()
        end_times = [ceiling_to_day(self.realm.date_created) + timedelta(days=i) for i in range(-1, 4)]
        self.assertEqual(data['end_times'], [datetime_to_timestamp(dt) for dt in end_times])
        self.assertEqual(data['everyone'], {'_1day': [0, *self.data(100)], '_15day': [0, *self.data(100)], 'all_time': [0, *self.data(100)]})

    def test_non_existent_chart(self) -> None:
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'does_not_exist'})
        self.assert_json_error_contains(result, 'Unknown chart name')

    def test_analytics_not_running(self) -> None:
        realm = get_realm("zulip")

        self.assertEqual(FillState.objects.count(), 0)

        realm.date_created = timezone_now() - timedelta(days=3)
        realm.save(update_fields=["date_created"])
        with self.assertLogs(level="WARNING") as m:
            result = self.client_get('/json/analytics/chart_data', {'chart_name': 'messages_sent_over_time'})
            self.assertEqual(m.output, [f"WARNING:root:User from realm zulip attempted to access /stats, but the computed start time: {realm.date_created} (creation of realm or installation) is later than the computed end time: 0001-01-01 00:00:00+00:00 (last successful analytics update). Is the analytics cron job running?"])

        self.assert_json_error_contains(result, 'No analytics data available')

        realm.date_created = timezone_now() - timedelta(days=1, hours=2)
        realm.save(update_fields=["date_created"])
        with self.assertLogs(level="WARNING") as m:
            result = self.client_get('/json/analytics/chart_data',
                                     {'chart_name': 'messages_sent_over_time'})
            self.assertEqual(m.output, [f"WARNING:root:User from realm zulip attempted to access /stats, but the computed start time: {realm.date_created} (creation of realm or installation) is later than the computed end time: 0001-01-01 00:00:00+00:00 (last successful analytics update). Is the analytics cron job running?"])

        self.assert_json_error_contains(result, 'No analytics data available')

        realm.date_created = timezone_now() - timedelta(days=1, minutes=10)
        realm.save(update_fields=["date_created"])
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'messages_sent_over_time'})
        self.assert_json_success(result)

        realm.date_created = timezone_now() - timedelta(hours=10)
        realm.save(update_fields=["date_created"])
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'messages_sent_over_time'})
        self.assert_json_success(result)

        end_time = timezone_now() - timedelta(days=5)
        fill_state = FillState.objects.create(property='messages_sent:is_bot:hour', end_time=end_time,
                                              state=FillState.DONE)

        realm.date_created = timezone_now() - timedelta(days=3)
        realm.save(update_fields=["date_created"])
        with self.assertLogs(level="WARNING") as m:
            result = self.client_get('/json/analytics/chart_data',
                                     {'chart_name': 'messages_sent_over_time'})
            self.assertEqual(m.output, [f"WARNING:root:User from realm zulip attempted to access /stats, but the computed start time: {realm.date_created} (creation of realm or installation) is later than the computed end time: {end_time} (last successful analytics update). Is the analytics cron job running?"])

        self.assert_json_error_contains(result, 'No analytics data available')

        realm.date_created = timezone_now() - timedelta(days=1, minutes=10)
        realm.save(update_fields=["date_created"])
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'messages_sent_over_time'})
        self.assert_json_success(result)

        end_time = timezone_now() - timedelta(days=2)
        fill_state.end_time = end_time
        fill_state.save(update_fields=["end_time"])

        realm.date_created = timezone_now() - timedelta(days=3)
        realm.save(update_fields=["date_created"])
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'messages_sent_over_time'})
        self.assert_json_success(result)

        realm.date_created = timezone_now() - timedelta(days=1, hours=2)
        realm.save(update_fields=["date_created"])
        with self.assertLogs(level="WARNING") as m:
            result = self.client_get('/json/analytics/chart_data',
                                     {'chart_name': 'messages_sent_over_time'})
            self.assertEqual(m.output, [f"WARNING:root:User from realm zulip attempted to access /stats, but the computed start time: {realm.date_created} (creation of realm or installation) is later than the computed end time: {end_time} (last successful analytics update). Is the analytics cron job running?"])

        self.assert_json_error_contains(result, 'No analytics data available')

        realm.date_created = timezone_now() - timedelta(days=1, minutes=10)
        realm.save(update_fields=["date_created"])
        result = self.client_get('/json/analytics/chart_data', {'chart_name': 'messages_sent_over_time'})
        self.assert_json_success(result)

    def test_get_chart_data_for_realm(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        result = self.client_get('/json/analytics/chart_data/realm/zulip',
                                 {'chart_name': 'number_of_humans'})
        self.assert_json_error(result, "Must be an server administrator", 400)

        user = self.example_user('hamlet')
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        stat = COUNT_STATS['realm_active_humans::day']
        self.insert_data(stat, [None], [])

        result = self.client_get('/json/analytics/chart_data/realm/not_existing_realm',
                                 {'chart_name': 'number_of_humans'})
        self.assert_json_error(result, 'Invalid organization', 400)

        result = self.client_get('/json/analytics/chart_data/realm/zulip',
                                 {'chart_name': 'number_of_humans'})
        self.assert_json_success(result)

    def test_get_chart_data_for_installation(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        result = self.client_get('/json/analytics/chart_data/installation',
                                 {'chart_name': 'number_of_humans'})
        self.assert_json_error(result, "Must be an server administrator", 400)

        user = self.example_user('hamlet')
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        stat = COUNT_STATS['realm_active_humans::day']
        self.insert_data(stat, [None], [])

        result = self.client_get('/json/analytics/chart_data/installation',
                                 {'chart_name': 'number_of_humans'})
        self.assert_json_success(result)

class TestSupportEndpoint(ZulipTestCase):
    def test_search(self) -> None:
        reset_emails_in_zulip_realm()

        def check_hamlet_user_query_result(result: HttpResponse) -> None:
            self.assert_in_success_response(['<span class="label">user</span>\n', '<h3>King Hamlet</h3>',
                                             '<b>Email</b>: hamlet@zulip.com', '<b>Is active</b>: True<br>',
                                             '<b>Admins</b>: desdemona@zulip.com, iago@zulip.com\n',
                                             'class="copy-button" data-copytext="desdemona@zulip.com, iago@zulip.com"',
                                             ], result)

        def check_zulip_realm_query_result(result: HttpResponse) -> None:
            zulip_realm = get_realm("zulip")
            self.assert_in_success_response([f'<input type="hidden" name="realm_id" value="{zulip_realm.id}"',
                                             'Zulip Dev</h3>',
                                             '<option value="1" selected>Self hosted</option>',
                                             '<option value="2" >Limited</option>',
                                             'input type="number" name="discount" value="None"',
                                             '<option value="active" selected>Active</option>',
                                             '<option value="deactivated" >Deactivated</option>',
                                             'scrub-realm-button">',
                                             'data-string-id="zulip"'], result)

        def check_lear_realm_query_result(result: HttpResponse) -> None:
            lear_realm = get_realm("lear")
            self.assert_in_success_response([f'<input type="hidden" name="realm_id" value="{lear_realm.id}"',
                                             'Lear &amp; Co.</h3>',
                                             '<option value="1" selected>Self hosted</option>',
                                             '<option value="2" >Limited</option>',
                                             'input type="number" name="discount" value="None"',
                                             '<option value="active" selected>Active</option>',
                                             '<option value="deactivated" >Deactivated</option>',
                                             'scrub-realm-button">',
                                             'data-string-id="lear"',
                                             '<b>Name</b>: Zulip Standard',
                                             '<b>Status</b>: Active',
                                             '<b>Billing schedule</b>: Annual',
                                             '<b>Licenses</b>: 2/10 (Manual)',
                                             '<b>Price per license</b>: $80.0',
                                             '<b>Next invoice date</b>: 02 January 2017',
                                             '<option value="send_invoice" selected>',
                                             '<option value="charge_automatically" >'
                                             ], result)

        def check_preregistration_user_query_result(result: HttpResponse, email: str, invite: bool=False) -> None:
            self.assert_in_success_response(['<span class="label">preregistration user</span>\n',
                                             f'<b>Email</b>: {email}',
                                             ], result)
            if invite:
                self.assert_in_success_response(['<span class="label">invite</span>'], result)
                self.assert_in_success_response(['<b>Expires in</b>: 1\xa0week, 3',
                                                 '<b>Status</b>: Link has never been clicked'], result)
                self.assert_in_success_response([], result)
            else:
                self.assert_not_in_success_response(['<span class="label">invite</span>'], result)
                self.assert_in_success_response(['<b>Expires in</b>: 1\xa0day',
                                                 '<b>Status</b>: Link has never been clicked'], result)

        def check_realm_creation_query_result(result: HttpResponse, email: str) -> None:
            self.assert_in_success_response(['<span class="label">preregistration user</span>\n',
                                             '<span class="label">realm creation</span>\n',
                                             '<b>Link</b>: http://testserver/accounts/do_confirm/',
                                             '<b>Expires in</b>: 1\xa0day<br>\n',
                                             ], result)

        def check_multiuse_invite_link_query_result(result: HttpResponse) -> None:
            self.assert_in_success_response(['<span class="label">multiuse invite</span>\n',
                                             '<b>Link</b>: http://zulip.testserver/join/',
                                             '<b>Expires in</b>: 1\xa0week, 3',
                                             ], result)

        def check_realm_reactivation_link_query_result(result: HttpResponse) -> None:
            self.assert_in_success_response(['<span class="label">realm reactivation</span>\n',
                                             '<b>Link</b>: http://zulip.testserver/reactivate/',
                                             '<b>Expires in</b>: 1\xa0day',
                                             ], result)

        self.login('cordelia')

        result = self.client_get("/activity/support")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        self.login('iago')

        customer = Customer.objects.create(realm=get_realm("lear"), stripe_customer_id='cus_123')
        now = datetime(2016, 1, 2, tzinfo=timezone.utc)
        plan = CustomerPlan.objects.create(customer=customer, billing_cycle_anchor=now,
                                           billing_schedule=CustomerPlan.ANNUAL, tier=CustomerPlan.STANDARD,
                                           price_per_license=8000, next_invoice_date=add_months(now, 12))
        LicenseLedger.objects.create(licenses=10, licenses_at_next_renewal=10, event_time=timezone_now(),
                                     is_renewal=True, plan=plan)

        result = self.client_get("/activity/support")
        self.assert_in_success_response(['<input type="text" name="q" class="input-xxlarge search-query"'], result)

        result = self.client_get("/activity/support", {"q": "hamlet@zulip.com"})
        check_hamlet_user_query_result(result)
        check_zulip_realm_query_result(result)

        result = self.client_get("/activity/support", {"q": "lear"})
        check_lear_realm_query_result(result)

        result = self.client_get("/activity/support", {"q": "http://lear.testserver"})
        check_lear_realm_query_result(result)

        with self.settings(REALM_HOSTS={'zulip': 'localhost'}):
            result = self.client_get("/activity/support", {"q": "http://localhost"})
            check_zulip_realm_query_result(result)

        result = self.client_get("/activity/support", {"q": "hamlet@zulip.com, lear"})
        check_hamlet_user_query_result(result)
        check_zulip_realm_query_result(result)
        check_lear_realm_query_result(result)

        result = self.client_get("/activity/support", {"q": "lear, Hamlet <hamlet@zulip.com>"})
        check_hamlet_user_query_result(result)
        check_zulip_realm_query_result(result)
        check_lear_realm_query_result(result)

        self.client_post('/accounts/home/', {'email': self.nonreg_email("test")})
        self.login('iago')
        result = self.client_get("/activity/support", {"q": self.nonreg_email("test")})
        check_preregistration_user_query_result(result, self.nonreg_email("test"))
        check_zulip_realm_query_result(result)

        stream_ids = [self.get_stream_id("Denmark")]
        invitee_emails = [self.nonreg_email("test1")]
        self.client_post("/json/invites", {"invitee_emails": invitee_emails,
                                           "stream_ids": orjson.dumps(stream_ids).decode(),
                                           "invite_as": PreregistrationUser.INVITE_AS['MEMBER']})
        result = self.client_get("/activity/support", {"q": self.nonreg_email("test1")})
        check_preregistration_user_query_result(result, self.nonreg_email("test1"), invite=True)
        check_zulip_realm_query_result(result)

        email = self.nonreg_email('alice')
        self.client_post('/new/', {'email': email})
        result = self.client_get("/activity/support", {"q": email})
        check_realm_creation_query_result(result, email)

        do_create_multiuse_invite_link(self.example_user("hamlet"), invited_as=1)
        result = self.client_get("/activity/support", {"q": "zulip"})
        check_multiuse_invite_link_query_result(result)
        check_zulip_realm_query_result(result)
        MultiuseInvite.objects.all().delete()

        do_send_realm_reactivation_email(get_realm("zulip"))
        result = self.client_get("/activity/support", {"q": "zulip"})
        check_realm_reactivation_link_query_result(result)
        check_zulip_realm_query_result(result)

    @mock.patch("analytics.views.update_billing_method_of_current_plan")
    def test_change_billing_method(self, m: mock.Mock) -> None:
        cordelia = self.example_user('cordelia')
        self.login_user(cordelia)

        result = self.client_post("/activity/support", {"realm_id": f"{cordelia.realm_id}", "plan_type": "2"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        result = self.client_post("/activity/support", {"realm_id": f"{iago.realm_id}", "billing_method": "charge_automatically"})
        m.assert_called_once_with(get_realm("zulip"), charge_automatically=True)
        self.assert_in_success_response(["Billing method of zulip updated to charge automatically"], result)

        m.reset_mock()

        result = self.client_post("/activity/support", {"realm_id": f"{iago.realm_id}", "billing_method": "send_invoice"})
        m.assert_called_once_with(get_realm("zulip"), charge_automatically=False)
        self.assert_in_success_response(["Billing method of zulip updated to pay by invoice"], result)

    def test_change_plan_type(self) -> None:
        cordelia = self.example_user('cordelia')
        self.login_user(cordelia)

        result = self.client_post("/activity/support", {"realm_id": f"{cordelia.realm_id}", "plan_type": "2"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        with mock.patch("analytics.views.do_change_plan_type") as m:
            result = self.client_post("/activity/support", {"realm_id": f"{iago.realm_id}", "plan_type": "2"})
            m.assert_called_once_with(get_realm("zulip"), 2)
            self.assert_in_success_response(["Plan type of zulip changed from self hosted to limited"], result)

    def test_attach_discount(self) -> None:
        cordelia = self.example_user('cordelia')
        lear_realm = get_realm('lear')
        self.login_user(cordelia)

        result = self.client_post("/activity/support", {"realm_id": f"{lear_realm.id}", "discount": "25"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        self.login('iago')

        with mock.patch("analytics.views.attach_discount_to_realm") as m:
            result = self.client_post("/activity/support", {"realm_id": f"{lear_realm.id}", "discount": "25"})
            m.assert_called_once_with(get_realm("lear"), 25)
            self.assert_in_success_response(["Discount of lear changed to 25 from None"], result)

    def test_change_sponsorship_status(self) -> None:
        lear_realm = get_realm("lear")
        self.assertIsNone(get_customer_by_realm(lear_realm))

        cordelia = self.example_user('cordelia')
        self.login_user(cordelia)

        result = self.client_post("/activity/support", {"realm_id": f"{lear_realm.id}",
                                                        "sponsorship_pending": "true"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        result = self.client_post("/activity/support", {"realm_id": f"{lear_realm.id}",
                                                        "sponsorship_pending": "true"})
        self.assert_in_success_response(["lear marked as pending sponsorship."], result)
        customer = get_customer_by_realm(lear_realm)
        assert(customer is not None)
        self.assertTrue(customer.sponsorship_pending)

        result = self.client_post("/activity/support", {"realm_id": f"{lear_realm.id}",
                                                        "sponsorship_pending": "false"})
        self.assert_in_success_response(["lear is no longer pending sponsorship."], result)
        customer = get_customer_by_realm(lear_realm)
        assert(customer is not None)
        self.assertFalse(customer.sponsorship_pending)

    def test_approve_sponsorship(self) -> None:
        lear_realm = get_realm("lear")
        update_sponsorship_status(lear_realm, True)
        king_user = self.lear_user("king")
        king_user.role = UserProfile.ROLE_REALM_OWNER
        king_user.save()

        cordelia = self.example_user('cordelia')
        self.login_user(cordelia)

        result = self.client_post("/activity/support", {"realm_id": f"{lear_realm.id}",
                                                        "approve_sponsorship": "approve_sponsorship"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        result = self.client_post("/activity/support", {"realm_id": f"{lear_realm.id}",
                                                        "approve_sponsorship": "approve_sponsorship"})
        self.assert_in_success_response(["Sponsorship approved for lear"], result)
        lear_realm.refresh_from_db()
        self.assertEqual(lear_realm.plan_type, Realm.STANDARD_FREE)
        customer = get_customer_by_realm(lear_realm)
        assert(customer is not None)
        self.assertFalse(customer.sponsorship_pending)
        messages = UserMessage.objects.filter(user_profile=king_user)
        self.assertIn("request for sponsored hosting has been approved", messages[0].message.content)
        self.assertEqual(len(messages), 1)

    def test_activate_or_deactivate_realm(self) -> None:
        cordelia = self.example_user('cordelia')
        lear_realm = get_realm('lear')
        self.login_user(cordelia)

        result = self.client_post("/activity/support", {"realm_id": f"{lear_realm.id}", "status": "deactivated"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        self.login('iago')

        with mock.patch("analytics.views.do_deactivate_realm") as m:
            result = self.client_post("/activity/support", {"realm_id": f"{lear_realm.id}", "status": "deactivated"})
            m.assert_called_once_with(lear_realm, self.example_user("iago"))
            self.assert_in_success_response(["lear deactivated"], result)

        with mock.patch("analytics.views.do_send_realm_reactivation_email") as m:
            result = self.client_post("/activity/support", {"realm_id": f"{lear_realm.id}", "status": "active"})
            m.assert_called_once_with(lear_realm)
            self.assert_in_success_response(["Realm reactivation email sent to admins of lear"], result)

    def test_downgrade_realm(self) -> None:
        cordelia = self.example_user('cordelia')
        self.login_user(cordelia)
        result = self.client_post("/activity/support", {"realm_id": f"{cordelia.realm_id}", "plan_type": "2"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        with mock.patch("analytics.views.downgrade_at_the_end_of_billing_cycle") as m:
            result = self.client_post("/activity/support", {"realm_id": f"{iago.realm_id}",
                                      "downgrade_method": "downgrade_at_billing_cycle_end"})
            m.assert_called_once_with(get_realm("zulip"))
            self.assert_in_success_response(["zulip marked for downgrade at the end of billing cycle"], result)

        with mock.patch("analytics.views.downgrade_now_without_creating_additional_invoices") as m:
            result = self.client_post("/activity/support", {"realm_id": f"{iago.realm_id}",
                                      "downgrade_method": "downgrade_now_without_additional_licenses"})
            m.assert_called_once_with(get_realm("zulip"))
            self.assert_in_success_response(["zulip downgraded without creating additional invoices"], result)

        with mock.patch("analytics.views.downgrade_now_without_creating_additional_invoices") as m1:
            with mock.patch("analytics.views.void_all_open_invoices", return_value=1) as m2:
                result = self.client_post("/activity/support", {"realm_id": f"{iago.realm_id}",
                                          "downgrade_method": "downgrade_now_void_open_invoices"})
                m1.assert_called_once_with(get_realm("zulip"))
                m2.assert_called_once_with(get_realm("zulip"))
                self.assert_in_success_response(["zulip downgraded and voided 1 open invoices"], result)

    def test_scrub_realm(self) -> None:
        cordelia = self.example_user('cordelia')
        lear_realm = get_realm('lear')
        self.login_user(cordelia)

        result = self.client_post("/activity/support", {"realm_id": f"{lear_realm.id}", "discount": "25"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        self.login('iago')

        with mock.patch("analytics.views.do_scrub_realm") as m:
            result = self.client_post("/activity/support", {"realm_id": f"{lear_realm.id}", "scrub_realm": "scrub_realm"})
            m.assert_called_once_with(lear_realm, acting_user=self.example_user("iago"))
            self.assert_in_success_response(["lear scrubbed"], result)

        with mock.patch("analytics.views.do_scrub_realm") as m:
            result = self.client_post("/activity/support", {"realm_id": f"{lear_realm.id}"})
            self.assert_json_error(result, "Invalid parameters")
            m.assert_not_called()

class TestGetChartDataHelpers(ZulipTestCase):
    # last_successful_fill is in analytics/models.py, but get_chart_data is
    # the only function that uses it at the moment
    def test_last_successful_fill(self) -> None:
        self.assertIsNone(last_successful_fill('non-existant'))
        a_time = datetime(2016, 3, 14, 19, tzinfo=timezone.utc)
        one_hour_before = datetime(2016, 3, 14, 18, tzinfo=timezone.utc)
        fillstate = FillState.objects.create(property='property', end_time=a_time,
                                             state=FillState.DONE)
        self.assertEqual(last_successful_fill('property'), a_time)
        fillstate.state = FillState.STARTED
        fillstate.save()
        self.assertEqual(last_successful_fill('property'), one_hour_before)

    def test_sort_by_totals(self) -> None:
        empty: List[int] = []
        value_arrays = {'c': [0, 1], 'a': [9], 'b': [1, 1, 1], 'd': empty}
        self.assertEqual(sort_by_totals(value_arrays), ['a', 'b', 'c', 'd'])

    def test_sort_client_labels(self) -> None:
        data = {'everyone': {'a': [16], 'c': [15], 'b': [14], 'e': [13], 'd': [12], 'h': [11]},
                'user': {'a': [6], 'b': [5], 'd': [4], 'e': [3], 'f': [2], 'g': [1]}}
        self.assertEqual(sort_client_labels(data), ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'])

class TestTimeRange(ZulipTestCase):
    def test_time_range(self) -> None:
        HOUR = timedelta(hours=1)
        DAY = timedelta(days=1)

        a_time = datetime(2016, 3, 14, 22, 59, tzinfo=timezone.utc)
        floor_hour = datetime(2016, 3, 14, 22, tzinfo=timezone.utc)
        floor_day = datetime(2016, 3, 14, tzinfo=timezone.utc)

        # test start == end
        self.assertEqual(time_range(a_time, a_time, CountStat.HOUR, None), [])
        self.assertEqual(time_range(a_time, a_time, CountStat.DAY, None), [])
        # test start == end == boundary, and min_length == 0
        self.assertEqual(time_range(floor_hour, floor_hour, CountStat.HOUR, 0), [floor_hour])
        self.assertEqual(time_range(floor_day, floor_day, CountStat.DAY, 0), [floor_day])
        # test start and end on different boundaries
        self.assertEqual(time_range(floor_hour, floor_hour+HOUR, CountStat.HOUR, None),
                         [floor_hour, floor_hour+HOUR])
        self.assertEqual(time_range(floor_day, floor_day+DAY, CountStat.DAY, None),
                         [floor_day, floor_day+DAY])
        # test min_length
        self.assertEqual(time_range(floor_hour, floor_hour+HOUR, CountStat.HOUR, 4),
                         [floor_hour-2*HOUR, floor_hour-HOUR, floor_hour, floor_hour+HOUR])
        self.assertEqual(time_range(floor_day, floor_day+DAY, CountStat.DAY, 4),
                         [floor_day-2*DAY, floor_day-DAY, floor_day, floor_day+DAY])

class TestMapArrays(ZulipTestCase):
    def test_map_arrays(self) -> None:
        a = {'desktop app 1.0': [1, 2, 3],
             'desktop app 2.0': [10, 12, 13],
             'desktop app 3.0': [21, 22, 23],
             'website': [1, 2, 3],
             'ZulipiOS': [1, 2, 3],
             'ZulipElectron': [2, 5, 7],
             'ZulipMobile': [1, 5, 7],
             'ZulipPython': [1, 2, 3],
             'API: Python': [1, 2, 3],
             'SomethingRandom': [4, 5, 6],
             'ZulipGitHubWebhook': [7, 7, 9],
             'ZulipAndroid': [64, 63, 65]}
        result = rewrite_client_arrays(a)
        self.assertEqual(result,
                         {'Old desktop app': [32, 36, 39],
                          'Old iOS app': [1, 2, 3],
                          'Desktop app': [2, 5, 7],
                          'Mobile app': [1, 5, 7],
                          'Website': [1, 2, 3],
                          'Python API': [2, 4, 6],
                          'SomethingRandom': [4, 5, 6],
                          'GitHub webhook': [7, 7, 9],
                          'Old Android app': [64, 63, 65]})

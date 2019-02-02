from datetime import datetime, timedelta
from typing import List, Optional

import mock
from django.utils.timezone import utc

from analytics.lib.counts import COUNT_STATS, CountStat
from analytics.lib.time_utils import time_range
from analytics.models import FillState, \
    RealmCount, UserCount, last_successful_fill
from analytics.views import rewrite_client_arrays, \
    sort_by_totals, sort_client_labels
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import ceiling_to_day, \
    ceiling_to_hour, datetime_to_timestamp
from zerver.models import Client, get_realm

class TestStatsEndpoint(ZulipTestCase):
    def test_stats(self) -> None:
        self.user = self.example_user('hamlet')
        self.login(self.user.email)
        result = self.client_get('/stats')
        self.assertEqual(result.status_code, 200)
        # Check that we get something back
        self.assert_in_response("Zulip analytics for", result)

    def test_guest_user_cant_access_stats(self) -> None:
        self.user = self.example_user('polonius')
        self.login(self.user.email)
        result = self.client_get('/stats')
        self.assert_json_error(result, "Not allowed for guest users", 400)

        result = self.client_get('/json/analytics/chart_data')
        self.assert_json_error(result, "Not allowed for guest users", 400)

    def test_stats_for_realm(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)

        result = self.client_get('/stats/realm/zulip/')
        self.assertEqual(result.status_code, 302)

        user_profile = self.example_user('hamlet')
        user_profile.is_staff = True
        user_profile.save(update_fields=['is_staff'])

        result = self.client_get('/stats/realm/not_existing_realm/')
        self.assertEqual(result.status_code, 302)

        result = self.client_get('/stats/realm/zulip/')
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Zulip analytics for", result)

    def test_stats_for_installation(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)

        result = self.client_get('/stats/installation')
        self.assertEqual(result.status_code, 302)

        user_profile = self.example_user('hamlet')
        user_profile.is_staff = True
        user_profile.save(update_fields=['is_staff'])

        result = self.client_get('/stats/installation')
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Zulip analytics for", result)

class TestGetChartData(ZulipTestCase):
    def setUp(self) -> None:
        self.realm = get_realm('zulip')
        self.user = self.example_user('hamlet')
        self.login(self.user.email)
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

        RealmCount.objects.bulk_create([
            RealmCount(property=stat.property, subgroup=subgroup, end_time=insert_time,
                       value=100+i, realm=self.realm)
            for i, subgroup in enumerate(realm_subgroups)])
        UserCount.objects.bulk_create([
            UserCount(property=stat.property, subgroup=subgroup, end_time=insert_time,
                      value=200+i, realm=self.realm, user=self.user)
            for i, subgroup in enumerate(user_subgroups)])
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
        self.assertEqual(data['everyone'], {'_1day': [0]+self.data(100), '_15day': [0]+self.data(100), 'all_time': [0]+self.data(100)})

    def test_non_existent_chart(self) -> None:
        result = self.client_get('/json/analytics/chart_data',
                                 {'chart_name': 'does_not_exist'})
        self.assert_json_error_contains(result, 'Unknown chart name')

    def test_analytics_not_running(self) -> None:
        # try to get data for a valid chart, but before we've put anything in the database
        # (e.g. before update_analytics_counts has been run)
        with mock.patch('logging.warning'):
            result = self.client_get('/json/analytics/chart_data',
                                     {'chart_name': 'number_of_humans'})
        self.assert_json_error_contains(result, 'No analytics data available')

    def test_get_chart_data_for_realm(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)

        result = self.client_get('/json/analytics/chart_data/realm/zulip/',
                                 {'chart_name': 'number_of_humans'})
        self.assert_json_error(result, "Must be an server administrator", 400)

        user_profile = self.example_user('hamlet')
        user_profile.is_staff = True
        user_profile.save(update_fields=['is_staff'])
        stat = COUNT_STATS['realm_active_humans::day']
        self.insert_data(stat, [None], [])

        result = self.client_get('/json/analytics/chart_data/realm/not_existing_realm',
                                 {'chart_name': 'number_of_humans'})
        self.assert_json_error(result, 'Invalid organization', 400)

        result = self.client_get('/json/analytics/chart_data/realm/zulip',
                                 {'chart_name': 'number_of_humans'})
        self.assert_json_success(result)

    def test_get_chart_data_for_installation(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)

        result = self.client_get('/json/analytics/chart_data/installation',
                                 {'chart_name': 'number_of_humans'})
        self.assert_json_error(result, "Must be an server administrator", 400)

        user_profile = self.example_user('hamlet')
        user_profile.is_staff = True
        user_profile.save(update_fields=['is_staff'])
        stat = COUNT_STATS['realm_active_humans::day']
        self.insert_data(stat, [None], [])

        result = self.client_get('/json/analytics/chart_data/installation',
                                 {'chart_name': 'number_of_humans'})
        self.assert_json_success(result)

class TestGetChartDataHelpers(ZulipTestCase):
    # last_successful_fill is in analytics/models.py, but get_chart_data is
    # the only function that uses it at the moment
    def test_last_successful_fill(self) -> None:
        self.assertIsNone(last_successful_fill('non-existant'))
        a_time = datetime(2016, 3, 14, 19).replace(tzinfo=utc)
        one_hour_before = datetime(2016, 3, 14, 18).replace(tzinfo=utc)
        fillstate = FillState.objects.create(property='property', end_time=a_time,
                                             state=FillState.DONE)
        self.assertEqual(last_successful_fill('property'), a_time)
        fillstate.state = FillState.STARTED
        fillstate.save()
        self.assertEqual(last_successful_fill('property'), one_hour_before)

    def test_sort_by_totals(self) -> None:
        empty = []  # type: List[int]
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

        a_time = datetime(2016, 3, 14, 22, 59).replace(tzinfo=utc)
        floor_hour = datetime(2016, 3, 14, 22).replace(tzinfo=utc)
        floor_day = datetime(2016, 3, 14).replace(tzinfo=utc)

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


from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Text, Tuple, Type, Union

import ujson
from django.apps import apps
from django.db import models
from django.db.models import Sum
from django.test import TestCase
from django.utils.timezone import now as timezone_now
from django.utils.timezone import utc as timezone_utc

from analytics.lib.counts import COUNT_STATS, CountStat, DataCollector, \
    DependentCountStat, LoggingCountStat, do_aggregate_to_summary_table, \
    do_drop_all_analytics_tables, do_drop_single_stat, \
    do_fill_count_stat_at_hour, do_increment_logging_stat, \
    process_count_stat, sql_data_collector
from analytics.models import Anomaly, BaseCount, \
    FillState, InstallationCount, RealmCount, StreamCount, \
    UserCount, installation_epoch, last_successful_fill
from zerver.lib.actions import do_activate_user, do_create_user, \
    do_deactivate_user, do_reactivate_user, update_user_activity_interval, \
    do_invite_users, do_revoke_user_invite, do_resend_user_invite_email, \
    InvitationError
from zerver.lib.timestamp import TimezoneNotUTCException, floor_to_day
from zerver.models import Client, Huddle, Message, Realm, \
    RealmAuditLog, Recipient, Stream, UserActivityInterval, \
    UserProfile, get_client, get_user, PreregistrationUser

class AnalyticsTestCase(TestCase):
    MINUTE = timedelta(seconds = 60)
    HOUR = MINUTE * 60
    DAY = HOUR * 24
    TIME_ZERO = datetime(1988, 3, 14).replace(tzinfo=timezone_utc)
    TIME_LAST_HOUR = TIME_ZERO - HOUR

    def setUp(self) -> None:
        self.default_realm = Realm.objects.create(
            string_id='realmtest', name='Realm Test', date_created=self.TIME_ZERO - 2*self.DAY)
        # used to generate unique names in self.create_*
        self.name_counter = 100
        # used as defaults in self.assertCountEquals
        self.current_property = None  # type: Optional[str]

    # Lightweight creation of users, streams, and messages
    def create_user(self, **kwargs: Any) -> UserProfile:
        self.name_counter += 1
        defaults = {
            'email': 'user%s@domain.tld' % (self.name_counter,),
            'date_joined': self.TIME_LAST_HOUR,
            'full_name': 'full_name',
            'short_name': 'short_name',
            'pointer': -1,
            'last_pointer_updater': 'seems unused?',
            'realm': self.default_realm,
            'api_key': '42'}
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        return UserProfile.objects.create(**kwargs)

    def create_stream_with_recipient(self, **kwargs: Any) -> Tuple[Stream, Recipient]:
        self.name_counter += 1
        defaults = {'name': 'stream name %s' % (self.name_counter,),
                    'realm': self.default_realm,
                    'date_created': self.TIME_LAST_HOUR}
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        stream = Stream.objects.create(**kwargs)
        recipient = Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)
        return stream, recipient

    def create_huddle_with_recipient(self, **kwargs: Any) -> Tuple[Huddle, Recipient]:
        self.name_counter += 1
        defaults = {'huddle_hash': 'hash%s' % (self.name_counter,)}
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        huddle = Huddle.objects.create(**kwargs)
        recipient = Recipient.objects.create(type_id=huddle.id, type=Recipient.HUDDLE)
        return huddle, recipient

    def create_message(self, sender: UserProfile, recipient: Recipient, **kwargs: Any) -> Message:
        defaults = {
            'sender': sender,
            'recipient': recipient,
            'subject': 'subject',
            'content': 'hi',
            'pub_date': self.TIME_LAST_HOUR,
            'sending_client': get_client("website")}
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        return Message.objects.create(**kwargs)

    # kwargs should only ever be a UserProfile or Stream.
    def assertCountEquals(self, table: Type[BaseCount], value: int, property: Optional[Text]=None,
                          subgroup: Optional[Text]=None, end_time: datetime=TIME_ZERO,
                          realm: Optional[Realm]=None, **kwargs: models.Model) -> None:
        if property is None:
            property = self.current_property
        queryset = table.objects.filter(property=property, end_time=end_time).filter(**kwargs)
        if table is not InstallationCount:
            if realm is None:
                realm = self.default_realm
            queryset = queryset.filter(realm=realm)
        if subgroup is not None:
            queryset = queryset.filter(subgroup=subgroup)
        self.assertEqual(queryset.values_list('value', flat=True)[0], value)

    def assertTableState(self, table: Type[BaseCount], arg_keys: List[str],
                         arg_values: List[List[object]]) -> None:
        """Assert that the state of a *Count table is what it should be.

        Example usage:
            self.assertTableState(RealmCount, ['property', 'subgroup', 'realm'],
                                  [['p1', 4], ['p2', 10, self.alt_realm]])

        table -- A *Count table.
        arg_keys -- List of columns of <table>.
        arg_values -- List of "rows" of <table>.
            Each entry of arg_values (e.g. ['p1', 4]) represents a row of <table>.
            The i'th value of the entry corresponds to the i'th arg_key, so e.g.
            the first arg_values entry here corresponds to a row of RealmCount
            with property='p1' and subgroup=10.
            Any columns not specified (in this case, every column of RealmCount
            other than property and subgroup) are either set to default values,
            or are ignored.

        The function checks that every entry of arg_values matches exactly one
        row of <table>, and that no additional rows exist. Note that this means
        checking a table with duplicate rows is not supported.
        """
        defaults = {
            'property': self.current_property,
            'subgroup': None,
            'end_time': self.TIME_ZERO,
            'value': 1}
        for values in arg_values:
            kwargs = {}  # type: Dict[str, Any]
            for i in range(len(values)):
                kwargs[arg_keys[i]] = values[i]
            for key, value in defaults.items():
                kwargs[key] = kwargs.get(key, value)
            if table is not InstallationCount:
                if 'realm' not in kwargs:
                    if 'user' in kwargs:
                        kwargs['realm'] = kwargs['user'].realm
                    elif 'stream' in kwargs:
                        kwargs['realm'] = kwargs['stream'].realm
                    else:
                        kwargs['realm'] = self.default_realm
            self.assertEqual(table.objects.filter(**kwargs).count(), 1)
        self.assertEqual(table.objects.count(), len(arg_values))

class TestProcessCountStat(AnalyticsTestCase):
    def make_dummy_count_stat(self, property: str) -> CountStat:
        query = """INSERT INTO analytics_realmcount (realm_id, value, property, end_time)
                   VALUES (%s, 1, '%s', %%%%(time_end)s)""" % (self.default_realm.id, property)
        return CountStat(property, sql_data_collector(RealmCount, query, None), CountStat.HOUR)

    def assertFillStateEquals(self, stat: CountStat, end_time: datetime,
                              state: int=FillState.DONE) -> None:
        fill_state = FillState.objects.filter(property=stat.property).first()
        self.assertEqual(fill_state.end_time, end_time)
        self.assertEqual(fill_state.state, state)

    def test_process_stat(self) -> None:
        # process new stat
        current_time = installation_epoch() + self.HOUR
        stat = self.make_dummy_count_stat('test stat')
        process_count_stat(stat, current_time)
        self.assertFillStateEquals(stat, current_time)
        self.assertEqual(InstallationCount.objects.filter(property=stat.property).count(), 1)

        # dirty stat
        FillState.objects.filter(property=stat.property).update(state=FillState.STARTED)
        process_count_stat(stat, current_time)
        self.assertFillStateEquals(stat, current_time)
        self.assertEqual(InstallationCount.objects.filter(property=stat.property).count(), 1)

        # clean stat, no update
        process_count_stat(stat, current_time)
        self.assertFillStateEquals(stat, current_time)
        self.assertEqual(InstallationCount.objects.filter(property=stat.property).count(), 1)

        # clean stat, with update
        current_time = current_time + self.HOUR
        stat = self.make_dummy_count_stat('test stat')
        process_count_stat(stat, current_time)
        self.assertFillStateEquals(stat, current_time)
        self.assertEqual(InstallationCount.objects.filter(property=stat.property).count(), 2)

    def test_bad_fill_to_time(self) -> None:
        stat = self.make_dummy_count_stat('test stat')
        with self.assertRaises(ValueError):
            process_count_stat(stat, installation_epoch() + 65*self.MINUTE)
        with self.assertRaises(TimezoneNotUTCException):
            process_count_stat(stat, installation_epoch().replace(tzinfo=None))

    # This tests the LoggingCountStat branch of the code in do_delete_counts_at_hour.
    # It is important that do_delete_counts_at_hour not delete any of the collected
    # logging data!
    def test_process_logging_stat(self) -> None:
        end_time = self.TIME_ZERO

        user_stat = LoggingCountStat('user stat', UserCount, CountStat.DAY)
        stream_stat = LoggingCountStat('stream stat', StreamCount, CountStat.DAY)
        realm_stat = LoggingCountStat('realm stat', RealmCount, CountStat.DAY)
        user = self.create_user()
        stream = self.create_stream_with_recipient()[0]
        realm = self.default_realm
        UserCount.objects.create(
            user=user, realm=realm, property=user_stat.property, end_time=end_time, value=5)
        StreamCount.objects.create(
            stream=stream, realm=realm, property=stream_stat.property, end_time=end_time, value=5)
        RealmCount.objects.create(
            realm=realm, property=realm_stat.property, end_time=end_time, value=5)

        # Normal run of process_count_stat
        for stat in [user_stat, stream_stat, realm_stat]:
            process_count_stat(stat, end_time)
        self.assertTableState(UserCount, ['property', 'value'], [[user_stat.property, 5]])
        self.assertTableState(StreamCount, ['property', 'value'], [[stream_stat.property, 5]])
        self.assertTableState(RealmCount, ['property', 'value'],
                              [[user_stat.property, 5],
                               [stream_stat.property, 5],
                               [realm_stat.property, 5]])
        self.assertTableState(InstallationCount, ['property', 'value'],
                              [[user_stat.property, 5],
                               [stream_stat.property, 5],
                               [realm_stat.property, 5]])

        # Change the logged data and mark FillState as dirty
        UserCount.objects.update(value=6)
        StreamCount.objects.update(value=6)
        RealmCount.objects.filter(property=realm_stat.property).update(value=6)
        FillState.objects.update(state=FillState.STARTED)

        # Check that the change propagated (and the collected data wasn't deleted)
        for stat in [user_stat, stream_stat, realm_stat]:
            process_count_stat(stat, end_time)
        self.assertTableState(UserCount, ['property', 'value'], [[user_stat.property, 6]])
        self.assertTableState(StreamCount, ['property', 'value'], [[stream_stat.property, 6]])
        self.assertTableState(RealmCount, ['property', 'value'],
                              [[user_stat.property, 6],
                               [stream_stat.property, 6],
                               [realm_stat.property, 6]])
        self.assertTableState(InstallationCount, ['property', 'value'],
                              [[user_stat.property, 6],
                               [stream_stat.property, 6],
                               [realm_stat.property, 6]])

    def test_process_dependent_stat(self) -> None:
        stat1 = self.make_dummy_count_stat('stat1')
        stat2 = self.make_dummy_count_stat('stat2')
        query = """INSERT INTO analytics_realmcount (realm_id, value, property, end_time)
                   VALUES (%s, 1, '%s', %%%%(time_end)s)""" % (self.default_realm.id, 'stat3')
        stat3 = DependentCountStat('stat3', sql_data_collector(RealmCount, query, None),
                                   CountStat.HOUR,
                                   dependencies=['stat1', 'stat2'])
        hour = [installation_epoch() + i*self.HOUR for i in range(5)]

        # test when one dependency has been run, and the other hasn't
        process_count_stat(stat1, hour[2])
        process_count_stat(stat3, hour[1])
        self.assertTableState(InstallationCount, ['property', 'end_time'],
                              [['stat1', hour[1]], ['stat1', hour[2]]])
        self.assertFillStateEquals(stat3, hour[0])

        # test that we don't fill past the fill_to_time argument, even if
        # dependencies have later last_successful_fill
        process_count_stat(stat2, hour[3])
        process_count_stat(stat3, hour[1])
        self.assertTableState(InstallationCount, ['property', 'end_time'],
                              [['stat1', hour[1]], ['stat1', hour[2]],
                               ['stat2', hour[1]], ['stat2', hour[2]], ['stat2', hour[3]],
                               ['stat3', hour[1]]])
        self.assertFillStateEquals(stat3, hour[1])

        # test that we don't fill past the dependency last_successful_fill times,
        # even if fill_to_time is later
        process_count_stat(stat3, hour[4])
        self.assertTableState(InstallationCount, ['property', 'end_time'],
                              [['stat1', hour[1]], ['stat1', hour[2]],
                               ['stat2', hour[1]], ['stat2', hour[2]], ['stat2', hour[3]],
                               ['stat3', hour[1]], ['stat3', hour[2]]])
        self.assertFillStateEquals(stat3, hour[2])

        # test daily dependent stat with hourly dependencies
        query = """INSERT INTO analytics_realmcount (realm_id, value, property, end_time)
                   VALUES (%s, 1, '%s', %%%%(time_end)s)""" % (self.default_realm.id, 'stat4')
        stat4 = DependentCountStat('stat4', sql_data_collector(RealmCount, query, None),
                                   CountStat.DAY,
                                   dependencies=['stat1', 'stat2'])
        hour24 = installation_epoch() + 24*self.HOUR
        hour25 = installation_epoch() + 25*self.HOUR
        process_count_stat(stat1, hour25)
        process_count_stat(stat2, hour25)
        process_count_stat(stat4, hour25)
        self.assertEqual(InstallationCount.objects.filter(property='stat4').count(), 1)
        self.assertFillStateEquals(stat4, hour24)

class TestCountStats(AnalyticsTestCase):
    def setUp(self) -> None:
        super().setUp()
        # This tests two things for each of the queries/CountStats: Handling
        # more than 1 realm, and the time bounds (time_start and time_end in
        # the queries).
        self.second_realm = Realm.objects.create(
            string_id='second-realm', name='Second Realm',
            date_created=self.TIME_ZERO-2*self.DAY)
        for minutes_ago in [0, 1, 61, 60*24+1]:
            creation_time = self.TIME_ZERO - minutes_ago*self.MINUTE
            user = self.create_user(email='user-%s@second.analytics' % (minutes_ago,),
                                    realm=self.second_realm, date_joined=creation_time)
            recipient = self.create_stream_with_recipient(
                name='stream %s' % (minutes_ago,), realm=self.second_realm,
                date_created=creation_time)[1]
            self.create_message(user, recipient, pub_date=creation_time)
        self.hourly_user = get_user('user-1@second.analytics', self.second_realm)
        self.daily_user = get_user('user-61@second.analytics', self.second_realm)

        # This realm should not show up in the *Count tables for any of the
        # messages_* CountStats
        self.no_message_realm = Realm.objects.create(
            string_id='no-message-realm', name='No Message Realm',
            date_created=self.TIME_ZERO-2*self.DAY)
        self.create_user(realm=self.no_message_realm)
        self.create_stream_with_recipient(realm=self.no_message_realm)
        # This huddle should not show up anywhere
        self.create_huddle_with_recipient()

    def test_active_users_by_is_bot(self) -> None:
        stat = COUNT_STATS['active_users:is_bot:day']
        self.current_property = stat.property

        # To be included
        self.create_user(is_bot=True)
        self.create_user(is_bot=True, date_joined=self.TIME_ZERO-25*self.HOUR)
        self.create_user(is_bot=False)

        # To be excluded
        self.create_user(is_active=False)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)

        self.assertTableState(RealmCount, ['value', 'subgroup', 'realm'],
                              [[2, 'true'], [1, 'false'],
                               [3, 'false', self.second_realm],
                               [1, 'false', self.no_message_realm]])
        self.assertTableState(InstallationCount,
                              ['value', 'subgroup'],
                              [[2, 'true'], [5, 'false']])
        self.assertTableState(UserCount, [], [])
        self.assertTableState(StreamCount, [], [])

    def test_messages_sent_by_is_bot(self) -> None:
        stat = COUNT_STATS['messages_sent:is_bot:hour']
        self.current_property = stat.property

        bot = self.create_user(is_bot=True)
        human1 = self.create_user()
        human2 = self.create_user()
        recipient_human1 = Recipient.objects.create(type_id=human1.id,
                                                    type=Recipient.PERSONAL)

        recipient_stream = self.create_stream_with_recipient()[1]
        recipient_huddle = self.create_huddle_with_recipient()[1]

        self.create_message(bot, recipient_human1)
        self.create_message(bot, recipient_stream)
        self.create_message(bot, recipient_huddle)
        self.create_message(human1, recipient_human1)
        self.create_message(human2, recipient_human1)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)

        self.assertTableState(UserCount, ['value', 'subgroup', 'user'],
                              [[1, 'false', human1], [1, 'false', human2], [3, 'true', bot],
                               [1, 'false', self.hourly_user]])
        self.assertTableState(RealmCount, ['value', 'subgroup', 'realm'],
                              [[2, 'false'], [3, 'true'], [1, 'false', self.second_realm]])
        self.assertTableState(InstallationCount, ['value', 'subgroup'], [[3, 'false'], [3, 'true']])
        self.assertTableState(StreamCount, [], [])

    def test_messages_sent_by_message_type(self) -> None:
        stat = COUNT_STATS['messages_sent:message_type:day']
        self.current_property = stat.property

        # Nothing currently in this stat that is bot related, but so many of
        # the rest of our stats make the human/bot distinction that one can
        # imagine a later refactoring that will intentionally or
        # unintentionally change this. So make one of our users a bot.
        user1 = self.create_user(is_bot=True)
        user2 = self.create_user()
        user3 = self.create_user()

        # private streams
        recipient_stream1 = self.create_stream_with_recipient(invite_only=True)[1]
        recipient_stream2 = self.create_stream_with_recipient(invite_only=True)[1]
        self.create_message(user1, recipient_stream1)
        self.create_message(user2, recipient_stream1)
        self.create_message(user2, recipient_stream2)

        # public streams
        recipient_stream3 = self.create_stream_with_recipient()[1]
        recipient_stream4 = self.create_stream_with_recipient()[1]
        self.create_message(user1, recipient_stream3)
        self.create_message(user1, recipient_stream4)
        self.create_message(user2, recipient_stream3)

        # huddles
        recipient_huddle1 = self.create_huddle_with_recipient()[1]
        recipient_huddle2 = self.create_huddle_with_recipient()[1]
        self.create_message(user1, recipient_huddle1)
        self.create_message(user2, recipient_huddle2)

        # private messages
        recipient_user1 = Recipient.objects.create(type_id=user1.id, type=Recipient.PERSONAL)
        recipient_user2 = Recipient.objects.create(type_id=user2.id, type=Recipient.PERSONAL)
        recipient_user3 = Recipient.objects.create(type_id=user3.id, type=Recipient.PERSONAL)
        self.create_message(user1, recipient_user2)
        self.create_message(user2, recipient_user1)
        self.create_message(user3, recipient_user3)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)

        self.assertTableState(UserCount, ['value', 'subgroup', 'user'],
                              [[1, 'private_stream', user1],
                               [2, 'private_stream', user2],
                               [2, 'public_stream', user1],
                               [1, 'public_stream', user2],
                               [1, 'private_message', user1],
                               [1, 'private_message', user2],
                               [1, 'private_message', user3],
                               [1, 'huddle_message', user1],
                               [1, 'huddle_message', user2],
                               [1, 'public_stream', self.hourly_user],
                               [1, 'public_stream', self.daily_user]])
        self.assertTableState(RealmCount, ['value', 'subgroup', 'realm'],
                              [[3, 'private_stream'], [3, 'public_stream'], [3, 'private_message'],
                               [2, 'huddle_message'], [2, 'public_stream', self.second_realm]])
        self.assertTableState(InstallationCount, ['value', 'subgroup'],
                              [[3, 'private_stream'], [5, 'public_stream'], [3, 'private_message'],
                               [2, 'huddle_message']])
        self.assertTableState(StreamCount, [], [])

    def test_messages_sent_to_recipients_with_same_id(self) -> None:
        stat = COUNT_STATS['messages_sent:message_type:day']
        self.current_property = stat.property

        user = self.create_user(id=1000)
        user_recipient = Recipient.objects.create(type_id=user.id, type=Recipient.PERSONAL)
        stream_recipient = self.create_stream_with_recipient(id=1000)[1]
        huddle_recipient = self.create_huddle_with_recipient(id=1000)[1]

        self.create_message(user, user_recipient)
        self.create_message(user, stream_recipient)
        self.create_message(user, huddle_recipient)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)

        self.assertCountEquals(UserCount, 1, subgroup='private_message')
        self.assertCountEquals(UserCount, 1, subgroup='huddle_message')
        self.assertCountEquals(UserCount, 1, subgroup='public_stream')

    def test_messages_sent_by_client(self) -> None:
        stat = COUNT_STATS['messages_sent:client:day']
        self.current_property = stat.property

        user1 = self.create_user(is_bot=True)
        user2 = self.create_user()
        recipient_user2 = Recipient.objects.create(type_id=user2.id, type=Recipient.PERSONAL)

        recipient_stream = self.create_stream_with_recipient()[1]
        recipient_huddle = self.create_huddle_with_recipient()[1]

        client2 = Client.objects.create(name='client2')

        self.create_message(user1, recipient_user2, sending_client=client2)
        self.create_message(user1, recipient_stream)
        self.create_message(user1, recipient_huddle)
        self.create_message(user2, recipient_user2, sending_client=client2)
        self.create_message(user2, recipient_user2, sending_client=client2)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)

        client2_id = str(client2.id)
        website_client_id = str(get_client('website').id)  # default for self.create_message
        self.assertTableState(UserCount, ['value', 'subgroup', 'user'],
                              [[2, website_client_id, user1],
                               [1, client2_id, user1], [2, client2_id, user2],
                               [1, website_client_id, self.hourly_user],
                               [1, website_client_id, self.daily_user]])
        self.assertTableState(RealmCount, ['value', 'subgroup', 'realm'],
                              [[2, website_client_id], [3, client2_id],
                               [2, website_client_id, self.second_realm]])
        self.assertTableState(InstallationCount, ['value', 'subgroup'],
                              [[4, website_client_id], [3, client2_id]])
        self.assertTableState(StreamCount, [], [])

    def test_messages_sent_to_stream_by_is_bot(self) -> None:
        stat = COUNT_STATS['messages_in_stream:is_bot:day']
        self.current_property = stat.property

        bot = self.create_user(is_bot=True)
        human1 = self.create_user()
        human2 = self.create_user()
        recipient_human1 = Recipient.objects.create(type_id=human1.id, type=Recipient.PERSONAL)

        stream1, recipient_stream1 = self.create_stream_with_recipient()
        stream2, recipient_stream2 = self.create_stream_with_recipient()

        # To be included
        self.create_message(human1, recipient_stream1)
        self.create_message(human2, recipient_stream1)
        self.create_message(human1, recipient_stream2)
        self.create_message(bot, recipient_stream2)
        self.create_message(bot, recipient_stream2)

        # To be excluded
        self.create_message(human2, recipient_human1)
        self.create_message(bot, recipient_human1)
        recipient_huddle = self.create_huddle_with_recipient()[1]
        self.create_message(human1, recipient_huddle)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)

        self.assertTableState(StreamCount, ['value', 'subgroup', 'stream'],
                              [[2, 'false', stream1], [1, 'false', stream2], [2, 'true', stream2],
                               # "hourly" and "daily" stream, from TestCountStats.setUp
                               [1, 'false', Stream.objects.get(name='stream 1')],
                               [1, 'false', Stream.objects.get(name='stream 61')]])
        self.assertTableState(RealmCount, ['value', 'subgroup', 'realm'],
                              [[3, 'false'], [2, 'true'], [2, 'false', self.second_realm]])
        self.assertTableState(InstallationCount, ['value', 'subgroup'], [[5, 'false'], [2, 'true']])
        self.assertTableState(UserCount, [], [])

    def create_interval(self, user: UserProfile, start_offset: timedelta,
                        end_offset: timedelta) -> None:
        UserActivityInterval.objects.create(
            user_profile=user, start=self.TIME_ZERO-start_offset,
            end=self.TIME_ZERO-end_offset)

    def test_15day_actives(self) -> None:
        stat = COUNT_STATS['15day_actives::day']
        self.current_property = stat.property

        _15day = 15*self.DAY - UserActivityInterval.MIN_INTERVAL_LENGTH

        # Outside time range, should not appear. Also tests upper boundary.
        user1 = self.create_user()
        self.create_interval(user1, _15day + self.DAY, _15day + timedelta(seconds=1))
        self.create_interval(user1, timedelta(0), -self.HOUR)

        # On lower boundary, should appear
        user2 = self.create_user()
        self.create_interval(user2, _15day + self.DAY, _15day)

        # Multiple intervals, including one outside boundary
        user3 = self.create_user()
        self.create_interval(user3, 20*self.DAY, 19*self.DAY)
        self.create_interval(user3, 20*self.HOUR, 19*self.HOUR)
        self.create_interval(user3, 20*self.MINUTE, 19*self.MINUTE)

        # Intervals crossing boundary
        user4 = self.create_user()
        self.create_interval(user4, 20*self.DAY, 10*self.DAY)
        user5 = self.create_user()
        self.create_interval(user5, self.MINUTE, -self.MINUTE)

        # Interval subsuming time range
        user6 = self.create_user()
        self.create_interval(user6, 20*self.DAY, -2*self.DAY)

        # Second realm
        user7 = self.create_user(realm=self.second_realm)
        self.create_interval(user7, 20*self.MINUTE, 19*self.MINUTE)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ['value', 'user'],
                              [[1, user2], [1, user3], [1, user4], [1, user5], [1, user6], [1, user7]])
        self.assertTableState(RealmCount, ['value', 'realm'],
                              [[5, self.default_realm], [1, self.second_realm]])
        self.assertTableState(InstallationCount, ['value'], [[6]])
        self.assertTableState(StreamCount, [], [])

    def test_minutes_active(self) -> None:
        stat = COUNT_STATS['minutes_active::day']
        self.current_property = stat.property

        # Outside time range, should not appear. Also testing for intervals
        # starting and ending on boundary
        user1 = self.create_user()
        self.create_interval(user1, 25*self.HOUR, self.DAY)
        self.create_interval(user1, timedelta(0), -self.HOUR)

        # Multiple intervals, including one outside boundary
        user2 = self.create_user()
        self.create_interval(user2, 20*self.DAY, 19*self.DAY)
        self.create_interval(user2, 20*self.HOUR, 19*self.HOUR)
        self.create_interval(user2, 20*self.MINUTE, 19*self.MINUTE)

        # Intervals crossing boundary
        user3 = self.create_user()
        self.create_interval(user3, 25*self.HOUR, 22*self.HOUR)
        self.create_interval(user3, self.MINUTE, -self.MINUTE)

        # Interval subsuming time range
        user4 = self.create_user()
        self.create_interval(user4, 2*self.DAY, -2*self.DAY)

        # Less than 60 seconds, should not appear
        user5 = self.create_user()
        self.create_interval(user5, self.MINUTE, timedelta(seconds=30))
        self.create_interval(user5, timedelta(seconds=20), timedelta(seconds=10))

        # Second realm
        user6 = self.create_user(realm=self.second_realm)
        self.create_interval(user6, 20*self.MINUTE, 19*self.MINUTE)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ['value', 'user'],
                              [[61, user2], [121, user3], [24*60, user4], [1, user6]])
        self.assertTableState(RealmCount, ['value', 'realm'],
                              [[61 + 121 + 24*60, self.default_realm], [1, self.second_realm]])
        self.assertTableState(InstallationCount, ['value'], [[61 + 121 + 24*60 + 1]])
        self.assertTableState(StreamCount, [], [])

class TestDoAggregateToSummaryTable(AnalyticsTestCase):
    # do_aggregate_to_summary_table is mostly tested by the end to end
    # nature of the tests in TestCountStats. But want to highlight one
    # feature important for keeping the size of the analytics tables small,
    # which is that if there is no relevant data in the table being
    # aggregated, the aggregation table doesn't get a row with value 0.
    def test_no_aggregated_zeros(self) -> None:
        stat = LoggingCountStat('test stat', UserCount, CountStat.HOUR)
        do_aggregate_to_summary_table(stat, self.TIME_ZERO)
        self.assertFalse(RealmCount.objects.exists())
        self.assertFalse(InstallationCount.objects.exists())

class TestDoIncrementLoggingStat(AnalyticsTestCase):
    def test_table_and_id_args(self) -> None:
        # For realms, streams, and users, tests that the new rows are going to
        # the appropriate *Count table, and that using a different zerver_object
        # results in a new row being created
        self.current_property = 'test'
        second_realm = Realm.objects.create(string_id='moo', name='moo')
        stat = LoggingCountStat('test', RealmCount, CountStat.DAY)
        do_increment_logging_stat(self.default_realm, stat, None, self.TIME_ZERO)
        do_increment_logging_stat(second_realm, stat, None, self.TIME_ZERO)
        self.assertTableState(RealmCount, ['realm'], [[self.default_realm], [second_realm]])

        user1 = self.create_user()
        user2 = self.create_user()
        stat = LoggingCountStat('test', UserCount, CountStat.DAY)
        do_increment_logging_stat(user1, stat, None, self.TIME_ZERO)
        do_increment_logging_stat(user2, stat, None, self.TIME_ZERO)
        self.assertTableState(UserCount, ['user'], [[user1], [user2]])

        stream1 = self.create_stream_with_recipient()[0]
        stream2 = self.create_stream_with_recipient()[0]
        stat = LoggingCountStat('test', StreamCount, CountStat.DAY)
        do_increment_logging_stat(stream1, stat, None, self.TIME_ZERO)
        do_increment_logging_stat(stream2, stat, None, self.TIME_ZERO)
        self.assertTableState(StreamCount, ['stream'], [[stream1], [stream2]])

    def test_frequency(self) -> None:
        times = [self.TIME_ZERO - self.MINUTE*i for i in [0, 1, 61, 24*60+1]]

        stat = LoggingCountStat('day test', RealmCount, CountStat.DAY)
        for time_ in times:
            do_increment_logging_stat(self.default_realm, stat, None, time_)
        stat = LoggingCountStat('hour test', RealmCount, CountStat.HOUR)
        for time_ in times:
            do_increment_logging_stat(self.default_realm, stat, None, time_)

        self.assertTableState(RealmCount, ['value', 'property', 'end_time'],
                              [[3, 'day test', self.TIME_ZERO],
                               [1, 'day test', self.TIME_ZERO - self.DAY],
                               [2, 'hour test', self.TIME_ZERO],
                               [1, 'hour test', self.TIME_LAST_HOUR],
                               [1, 'hour test', self.TIME_ZERO - self.DAY]])

    def test_get_or_create(self) -> None:
        stat = LoggingCountStat('test', RealmCount, CountStat.HOUR)
        # All these should trigger the create part of get_or_create.
        # property is tested in test_frequency, and id_args are tested in test_id_args,
        # so this only tests a new subgroup and end_time
        do_increment_logging_stat(self.default_realm, stat, 'subgroup1', self.TIME_ZERO)
        do_increment_logging_stat(self.default_realm, stat, 'subgroup2', self.TIME_ZERO)
        do_increment_logging_stat(self.default_realm, stat, 'subgroup1', self.TIME_LAST_HOUR)
        self.current_property = 'test'
        self.assertTableState(RealmCount, ['value', 'subgroup', 'end_time'],
                              [[1, 'subgroup1', self.TIME_ZERO], [1, 'subgroup2', self.TIME_ZERO],
                              [1, 'subgroup1', self.TIME_LAST_HOUR]])
        # This should trigger the get part of get_or_create
        do_increment_logging_stat(self.default_realm, stat, 'subgroup1', self.TIME_ZERO)
        self.assertTableState(RealmCount, ['value', 'subgroup', 'end_time'],
                              [[2, 'subgroup1', self.TIME_ZERO], [1, 'subgroup2', self.TIME_ZERO],
                              [1, 'subgroup1', self.TIME_LAST_HOUR]])

    def test_increment(self) -> None:
        stat = LoggingCountStat('test', RealmCount, CountStat.DAY)
        self.current_property = 'test'
        do_increment_logging_stat(self.default_realm, stat, None, self.TIME_ZERO, increment=-1)
        self.assertTableState(RealmCount, ['value'], [[-1]])
        do_increment_logging_stat(self.default_realm, stat, None, self.TIME_ZERO, increment=3)
        self.assertTableState(RealmCount, ['value'], [[2]])
        do_increment_logging_stat(self.default_realm, stat, None, self.TIME_ZERO)
        self.assertTableState(RealmCount, ['value'], [[3]])

class TestLoggingCountStats(AnalyticsTestCase):
    def test_aggregation(self) -> None:
        stat = LoggingCountStat('realm test', RealmCount, CountStat.DAY)
        do_increment_logging_stat(self.default_realm, stat, None, self.TIME_ZERO)
        process_count_stat(stat, self.TIME_ZERO)

        user = self.create_user()
        stat = LoggingCountStat('user test', UserCount, CountStat.DAY)
        do_increment_logging_stat(user, stat, None, self.TIME_ZERO)
        process_count_stat(stat, self.TIME_ZERO)

        stream = self.create_stream_with_recipient()[0]
        stat = LoggingCountStat('stream test', StreamCount, CountStat.DAY)
        do_increment_logging_stat(stream, stat, None, self.TIME_ZERO)
        process_count_stat(stat, self.TIME_ZERO)

        self.assertTableState(InstallationCount, ['property', 'value'],
                              [['realm test', 1], ['user test', 1], ['stream test', 1]])
        self.assertTableState(RealmCount, ['property', 'value'],
                              [['realm test', 1], ['user test', 1], ['stream test', 1]])
        self.assertTableState(UserCount, ['property', 'value'], [['user test', 1]])
        self.assertTableState(StreamCount, ['property', 'value'], [['stream test', 1]])

    def test_active_users_log_by_is_bot(self) -> None:
        property = 'active_users_log:is_bot:day'
        user = do_create_user('email', 'password', self.default_realm, 'full_name', 'short_name')
        self.assertEqual(1, RealmCount.objects.filter(property=property, subgroup=False)
                         .aggregate(Sum('value'))['value__sum'])
        do_deactivate_user(user)
        self.assertEqual(0, RealmCount.objects.filter(property=property, subgroup=False)
                         .aggregate(Sum('value'))['value__sum'])
        do_activate_user(user)
        self.assertEqual(1, RealmCount.objects.filter(property=property, subgroup=False)
                         .aggregate(Sum('value'))['value__sum'])
        do_deactivate_user(user)
        self.assertEqual(0, RealmCount.objects.filter(property=property, subgroup=False)
                         .aggregate(Sum('value'))['value__sum'])
        do_reactivate_user(user)
        self.assertEqual(1, RealmCount.objects.filter(property=property, subgroup=False)
                         .aggregate(Sum('value'))['value__sum'])

    def test_invites_sent(self) -> None:
        property = 'invites_sent::day'

        def assertInviteCountEquals(count: int) -> None:
            self.assertEqual(count, RealmCount.objects.filter(property=property, subgroup=None)
                             .aggregate(Sum('value'))['value__sum'])

        user = self.create_user(email='first@domain.tld')
        stream, _ = self.create_stream_with_recipient()
        do_invite_users(user, ['user1@domain.tld', 'user2@domain.tld'], [stream])
        assertInviteCountEquals(2)

        # We currently send emails when re-inviting users that haven't
        # turned into accounts, so count them towards the total
        do_invite_users(user, ['user1@domain.tld', 'user2@domain.tld'], [stream])
        assertInviteCountEquals(4)

        # Test mix of good and malformed invite emails
        try:
            do_invite_users(user, ['user3@domain.tld', 'malformed'], [stream])
        except InvitationError:
            pass
        assertInviteCountEquals(4)

        # Test inviting existing users
        try:
            do_invite_users(user, ['first@domain.tld', 'user4@domain.tld'], [stream])
        except InvitationError:
            pass
        assertInviteCountEquals(5)

        # Revoking invite should not give you credit
        do_revoke_user_invite(PreregistrationUser.objects.filter(realm=user.realm).first())
        assertInviteCountEquals(5)

        # Resending invite should cost you
        do_resend_user_invite_email(PreregistrationUser.objects.first())
        assertInviteCountEquals(6)

class TestDeleteStats(AnalyticsTestCase):
    def test_do_drop_all_analytics_tables(self) -> None:
        user = self.create_user()
        stream = self.create_stream_with_recipient()[0]
        count_args = {'property': 'test', 'end_time': self.TIME_ZERO, 'value': 10}

        UserCount.objects.create(user=user, realm=user.realm, **count_args)
        StreamCount.objects.create(stream=stream, realm=stream.realm, **count_args)
        RealmCount.objects.create(realm=user.realm, **count_args)
        InstallationCount.objects.create(**count_args)
        FillState.objects.create(property='test', end_time=self.TIME_ZERO, state=FillState.DONE)
        Anomaly.objects.create(info='test anomaly')

        analytics = apps.get_app_config('analytics')
        for table in list(analytics.models.values()):
            self.assertTrue(table.objects.exists())

        do_drop_all_analytics_tables()
        for table in list(analytics.models.values()):
            self.assertFalse(table.objects.exists())

    def test_do_drop_single_stat(self) -> None:
        user = self.create_user()
        stream = self.create_stream_with_recipient()[0]
        count_args_to_delete = {'property': 'to_delete', 'end_time': self.TIME_ZERO, 'value': 10}
        count_args_to_save = {'property': 'to_save', 'end_time': self.TIME_ZERO, 'value': 10}

        for count_args in [count_args_to_delete, count_args_to_save]:
            UserCount.objects.create(user=user, realm=user.realm, **count_args)
            StreamCount.objects.create(stream=stream, realm=stream.realm, **count_args)
            RealmCount.objects.create(realm=user.realm, **count_args)
            InstallationCount.objects.create(**count_args)
        FillState.objects.create(property='to_delete', end_time=self.TIME_ZERO, state=FillState.DONE)
        FillState.objects.create(property='to_save', end_time=self.TIME_ZERO, state=FillState.DONE)
        Anomaly.objects.create(info='test anomaly')

        analytics = apps.get_app_config('analytics')
        for table in list(analytics.models.values()):
            self.assertTrue(table.objects.exists())

        do_drop_single_stat('to_delete')
        for table in list(analytics.models.values()):
            if table._meta.db_table == 'analytics_anomaly':
                self.assertTrue(table.objects.exists())
            else:
                self.assertFalse(table.objects.filter(property='to_delete').exists())
                self.assertTrue(table.objects.filter(property='to_save').exists())

class TestActiveUsersAudit(AnalyticsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = self.create_user()
        self.stat = COUNT_STATS['active_users_audit:is_bot:day']
        self.current_property = self.stat.property

    def add_event(self, event_type: str, days_offset: float,
                  user: Optional[UserProfile]=None) -> None:
        hours_offset = int(24*days_offset)
        if user is None:
            user = self.user
        RealmAuditLog.objects.create(
            realm=user.realm, modified_user=user, event_type=event_type,
            event_time=self.TIME_ZERO - hours_offset*self.HOUR)

    def test_user_deactivated_in_future(self) -> None:
        self.add_event('user_created', 1)
        self.add_event('user_deactivated', 0)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ['subgroup'], [['false']])

    def test_user_reactivated_in_future(self) -> None:
        self.add_event('user_deactivated', 1)
        self.add_event('user_reactivated', 0)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, [], [])

    def test_user_active_then_deactivated_same_day(self) -> None:
        self.add_event('user_created', 1)
        self.add_event('user_deactivated', .5)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, [], [])

    def test_user_unactive_then_activated_same_day(self) -> None:
        self.add_event('user_deactivated', 1)
        self.add_event('user_reactivated', .5)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ['subgroup'], [['false']])

    # Arguably these next two tests are duplicates of the _in_future tests, but are
    # a guard against future refactorings where they may no longer be duplicates
    def test_user_active_then_deactivated_with_day_gap(self) -> None:
        self.add_event('user_created', 2)
        self.add_event('user_deactivated', 1)
        process_count_stat(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ['subgroup', 'end_time'],
                              [['false', self.TIME_ZERO - self.DAY]])

    def test_user_deactivated_then_reactivated_with_day_gap(self) -> None:
        self.add_event('user_deactivated', 2)
        self.add_event('user_reactivated', 1)
        process_count_stat(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ['subgroup'], [['false']])

    def test_event_types(self) -> None:
        self.add_event('user_created', 4)
        self.add_event('user_deactivated', 3)
        self.add_event('user_activated', 2)
        self.add_event('user_reactivated', 1)
        for i in range(4):
            do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO - i*self.DAY)
        self.assertTableState(UserCount, ['subgroup', 'end_time'],
                              [['false', self.TIME_ZERO - i*self.DAY] for i in [3, 1, 0]])

    # Also tests that aggregation to RealmCount and InstallationCount is
    # being done, and that we're storing the user correctly in UserCount
    def test_multiple_users_realms_and_bots(self) -> None:
        user1 = self.create_user()
        user2 = self.create_user()
        second_realm = Realm.objects.create(string_id='moo', name='moo')
        user3 = self.create_user(realm=second_realm)
        user4 = self.create_user(realm=second_realm, is_bot=True)
        for user in [user1, user2, user3, user4]:
            self.add_event('user_created', 1, user=user)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ['subgroup', 'user'],
                              [['false', user1], ['false', user2], ['false', user3], ['true', user4]])
        self.assertTableState(RealmCount, ['value', 'subgroup', 'realm'],
                              [[2, 'false', self.default_realm], [1, 'false', second_realm],
                               [1, 'true', second_realm]])
        self.assertTableState(InstallationCount, ['value', 'subgroup'], [[3, 'false'], [1, 'true']])
        self.assertTableState(StreamCount, [], [])

    # Not that interesting a test if you look at the SQL query at hand, but
    # almost all other CountStats have a start_date, so guarding against a
    # refactoring that adds that in.
    # Also tests the slightly more end-to-end process_count_stat rather than
    # do_fill_count_stat_at_hour. E.g. if one changes self.stat.frequency to
    # CountStat.HOUR from CountStat.DAY, this will fail, while many of the
    # tests above will not.
    def test_update_from_two_days_ago(self) -> None:
        self.add_event('user_created', 2)
        process_count_stat(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ['subgroup', 'end_time'],
                              [['false', self.TIME_ZERO], ['false', self.TIME_ZERO-self.DAY]])

    # User with no relevant activity could happen e.g. for a system bot that
    # doesn't go through do_create_user. Mainly just want to make sure that
    # that situation doesn't throw an error.
    def test_empty_realm_or_user_with_no_relevant_activity(self) -> None:
        self.add_event('unrelated', 1)
        self.create_user()  # also test a user with no RealmAuditLog entries
        Realm.objects.create(string_id='moo', name='moo')
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, [], [])

    def test_max_audit_entry_is_unrelated(self) -> None:
        self.add_event('user_created', 1)
        self.add_event('unrelated', .5)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ['subgroup'], [['false']])

    # Simultaneous related audit entries should not be allowed, and so not testing for that.
    def test_simultaneous_unrelated_audit_entry(self) -> None:
        self.add_event('user_created', 1)
        self.add_event('unrelated', 1)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ['subgroup'], [['false']])

    def test_simultaneous_max_audit_entries_of_different_users(self) -> None:
        user1 = self.create_user()
        user2 = self.create_user()
        user3 = self.create_user()
        self.add_event('user_created', .5, user=user1)
        self.add_event('user_created', .5, user=user2)
        self.add_event('user_created', 1, user=user3)
        self.add_event('user_deactivated', .5, user=user3)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ['user', 'subgroup'],
                              [[user1, 'false'], [user2, 'false']])

    def test_end_to_end_with_actions_dot_py(self) -> None:
        user1 = do_create_user('email1', 'password', self.default_realm, 'full_name', 'short_name')
        user2 = do_create_user('email2', 'password', self.default_realm, 'full_name', 'short_name')
        user3 = do_create_user('email3', 'password', self.default_realm, 'full_name', 'short_name')
        user4 = do_create_user('email4', 'password', self.default_realm, 'full_name', 'short_name')
        do_deactivate_user(user2)
        do_activate_user(user3)
        do_reactivate_user(user4)
        end_time = floor_to_day(timezone_now()) + self.DAY
        do_fill_count_stat_at_hour(self.stat, end_time)
        for user in [user1, user3, user4]:
            self.assertTrue(UserCount.objects.filter(
                user=user, property=self.current_property, subgroup='false',
                end_time=end_time, value=1).exists())
        self.assertFalse(UserCount.objects.filter(user=user2).exists())

class TestRealmActiveHumans(AnalyticsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stat = COUNT_STATS['realm_active_humans::day']
        self.current_property = self.stat.property

    def mark_audit_active(self, user: UserProfile, end_time: Optional[datetime]=None) -> None:
        if end_time is None:
            end_time = self.TIME_ZERO
        UserCount.objects.create(
            user=user, realm=user.realm, property='active_users_audit:is_bot:day',
            subgroup=ujson.dumps(user.is_bot), end_time=end_time, value=1)

    def mark_15day_active(self, user: UserProfile, end_time: Optional[datetime]=None) -> None:
        if end_time is None:
            end_time = self.TIME_ZERO
        UserCount.objects.create(
            user=user, realm=user.realm, property='15day_actives::day',
            end_time=end_time, value=1)

    def test_basic_boolean_logic(self) -> None:
        user = self.create_user()
        self.mark_audit_active(user, end_time=self.TIME_ZERO - self.DAY)
        self.mark_15day_active(user, end_time=self.TIME_ZERO)
        self.mark_audit_active(user, end_time=self.TIME_ZERO + self.DAY)
        self.mark_15day_active(user, end_time=self.TIME_ZERO + self.DAY)

        for i in [-1, 0, 1]:
            do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO + i*self.DAY)
        self.assertTableState(RealmCount, ['value', 'end_time'], [[1, self.TIME_ZERO + self.DAY]])

    def test_bots_not_counted(self) -> None:
        bot = self.create_user(is_bot=True)
        self.mark_audit_active(bot)
        self.mark_15day_active(bot)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(RealmCount, [], [])

    def test_multiple_users_realms_and_times(self) -> None:
        user1 = self.create_user()
        user2 = self.create_user()
        second_realm = Realm.objects.create(string_id='second', name='second')
        user3 = self.create_user(realm=second_realm)
        user4 = self.create_user(realm=second_realm)
        user5 = self.create_user(realm=second_realm)

        for user in [user1, user2, user3, user4, user5]:
            self.mark_audit_active(user)
            self.mark_15day_active(user)
        for user in [user1, user3, user4]:
            self.mark_audit_active(user, end_time=self.TIME_ZERO - self.DAY)
            self.mark_15day_active(user, end_time=self.TIME_ZERO - self.DAY)

        for i in [-1, 0, 1]:
            do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO + i*self.DAY)
        self.assertTableState(RealmCount, ['value', 'realm', 'end_time'],
                              [[2, self.default_realm, self.TIME_ZERO],
                               [3, second_realm, self.TIME_ZERO],
                               [1, self.default_realm, self.TIME_ZERO - self.DAY],
                               [2, second_realm, self.TIME_ZERO - self.DAY]])

        # Check that adding spurious entries doesn't make a difference
        self.mark_audit_active(user1, end_time=self.TIME_ZERO + self.DAY)
        self.mark_15day_active(user2, end_time=self.TIME_ZERO + self.DAY)
        self.mark_15day_active(user2, end_time=self.TIME_ZERO - self.DAY)
        self.create_user()
        third_realm = Realm.objects.create(string_id='third', name='third')
        self.create_user(realm=third_realm)

        RealmCount.objects.all().delete()
        for i in [-1, 0, 1]:
            do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO + i*self.DAY)
        self.assertTableState(RealmCount, ['value', 'realm', 'end_time'],
                              [[2, self.default_realm, self.TIME_ZERO],
                               [3, second_realm, self.TIME_ZERO],
                               [1, self.default_realm, self.TIME_ZERO - self.DAY],
                               [2, second_realm, self.TIME_ZERO - self.DAY]])

    def test_end_to_end(self) -> None:
        user1 = do_create_user('email1', 'password', self.default_realm, 'full_name', 'short_name')
        user2 = do_create_user('email2', 'password', self.default_realm, 'full_name', 'short_name')
        do_create_user('email3', 'password', self.default_realm, 'full_name', 'short_name')
        time_zero = floor_to_day(timezone_now()) + self.DAY
        update_user_activity_interval(user1, time_zero)
        update_user_activity_interval(user2, time_zero)
        do_deactivate_user(user2)
        for property in ['active_users_audit:is_bot:day', '15day_actives::day',
                         'realm_active_humans::day']:
            FillState.objects.create(property=property, state=FillState.DONE, end_time=time_zero)
            process_count_stat(COUNT_STATS[property], time_zero+self.DAY)
        self.assertEqual(RealmCount.objects.filter(
            property='realm_active_humans::day', end_time=time_zero+self.DAY, value=1).count(), 1)
        self.assertEqual(RealmCount.objects.filter(property='realm_active_humans::day').count(), 1)

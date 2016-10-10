from django.db import models
from django.test import TestCase
from django.utils import timezone

from analytics.lib.interval import TimeInterval
from analytics.lib.counts import CountStat, process_count_stat, \
    zerver_count_user_by_realm, zerver_count_message_by_user, \
    zerver_count_message_by_stream, zerver_count_stream_by_realm, \
    zerver_count_message_by_huddle
from analytics.models import BaseCount, InstallationCount, RealmCount, \
    UserCount, StreamCount

from zerver.models import Realm, UserProfile, Message, Stream, Recipient, \
    get_user_profile_by_email, get_client

from datetime import datetime, timedelta

from typing import Any, Type, Optional
from six import text_type

class AnalyticsTestCase(TestCase):
    MINUTE = timedelta(seconds = 60)
    HOUR = MINUTE * 60
    DAY = HOUR * 24
    TIME_ZERO = datetime(2042, 3, 14).replace(tzinfo=timezone.utc)
    TIME_LAST_HOUR = TIME_ZERO - HOUR

    def setUp(self):
        # type: () -> None
        self.default_realm = Realm.objects.create(domain='analytics.test', name='Realm Test',
                                                  date_created=self.TIME_ZERO - 2*self.DAY)

    def process_last_hour(self, stat):
        # type: (CountStat) -> None
        # The last two arguments below are eventually passed as the first and
        # last arguments of lib.interval.timeinterval_range, which is an
        # inclusive range.
        process_count_stat(stat, self.TIME_ZERO, self.TIME_ZERO)

    # Lightweight creation of users, streams, and messages
    def create_user(self, email, **kwargs):
        # type: (str, **Any) -> UserProfile
        defaults = {
            'date_joined': self.TIME_LAST_HOUR,
            'full_name': 'full_name',
            'short_name': 'short_name',
            'pointer': -1,
            'last_pointer_updater': 'seems unused?',
            'realm': self.default_realm,
            'api_key': '42'}
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        return UserProfile.objects.create(email=email, **kwargs)

    def create_stream(self, **kwargs):
        # type: (**Any) -> Stream
        defaults = {'name': 'stream name',
                    'realm': self.default_realm,
                    'date_created': self.TIME_LAST_HOUR}
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        return Stream.objects.create(**kwargs)

    def create_message(self, sender, recipient, **kwargs):
        # type: (UserProfile, Recipient, **Any) -> Message
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

    # Note that this doesn't work for InstallationCount, since InstallationCount has no realm_id
    # kwargs should only ever be a UserProfile or Stream.
    def assertCountEquals(self, table, property, value, end_time = TIME_ZERO, interval = 'hour',
                          realm = None, **kwargs):
        # type: (Type[BaseCount], text_type, int, datetime, str, Optional[Realm], **models.Model) -> None
        if realm is None:
            realm = self.default_realm
        self.assertEqual(table.objects.filter(realm=realm,
                                              property=property,
                                              interval=interval,
                                              end_time=end_time) \
                         .filter(**kwargs).values_list('value', flat=True)[0],
                         value)

# Tests manangement commands, backfilling, adding new stats, etc
class TestUpdateAnalyticsCounts(AnalyticsTestCase):
    def test_analytics_stat_write(self):
        # type: () -> None
        # might change if we refactor count_query

        stat = CountStat('test_stat_write', zerver_count_stream_by_realm,
                         {'invite_only': False}, 'hour', 'hour')

        # add some stuff to zerver_*
        self.create_stream(name='stream1')
        self.create_stream(name='stream2')
        self.create_stream(name='stream3')

        # run do_pull_from_zerver
        self.process_last_hour(stat)

        # check analytics_* values are correct
        self.assertCountEquals(RealmCount, 'test_stat_write', 3)

    def test_update_analytics_tables(self):
        # type: () -> None
        stat = CountStat('test_messages_sent', zerver_count_message_by_user, {}, 'hour', 'hour')

        user1 = self.create_user('email1')
        user2 = self.create_user('email2')
        recipient = Recipient.objects.create(type_id=user2.id, type=Recipient.PERSONAL)
        self.create_message(user1, recipient)

        # run command
        self.process_last_hour(stat)
        usercount_row = UserCount.objects.filter(realm=self.default_realm, interval='hour',
                                                 property='test_messages_sent').values_list(
            'value', flat=True)[0]
        assert (usercount_row == 1)

        # run command with dates before message creation
        process_count_stat(stat, range_start=self.TIME_ZERO - 2*self.HOUR,
                           range_end=self.TIME_LAST_HOUR)

        # check no earlier rows created, old ones still there
        self.assertFalse(UserCount.objects.filter(end_time__lt = self.TIME_ZERO - 2*self.HOUR).exists())
        self.assertCountEquals(UserCount, 'test_messages_sent', 1, user = user1)

class TestProcessCountStat(AnalyticsTestCase):
    # test users added in last hour
    def test_add_new_users(self):
        # type: () -> None
        stat = CountStat('add_new_user_test', zerver_count_user_by_realm, {}, 'hour', 'hour')

        # add new users to realm in last hour
        self.create_user('email1')
        self.create_user('email2')

        # add a new user before an hour
        self.create_user('email3', date_joined=self.TIME_ZERO - 2*self.HOUR)

        # check if user added before the hour is not included
        self.process_last_hour(stat)
        # do_update is writing the stat.property to all zerver tables

        self.assertCountEquals(RealmCount, 'add_new_user_test', 2)

    # test if process count does nothing if count already processed
    def test_process_count(self):
        # type: () -> None
        # add some active and inactive users that are human
        self.create_user('email1', is_bot=False, is_active=False)
        self.create_user('email2', is_bot=False, is_active=False)
        self.create_user('email3', is_bot=False, is_active=True)

        # run stat to pull active humans
        stat = CountStat('active_humans', zerver_count_user_by_realm,
                         {'is_bot': False, 'is_active': True}, 'hour', 'hour')

        self.process_last_hour(stat)
        self.assertCountEquals(RealmCount, 'active_humans', 1)

        # run command again
        self.process_last_hour(stat)

        # check that row is same as before
        self.assertCountEquals(RealmCount, 'active_humans', 1)

    def test_do_aggregate(self):
        # type: () -> None

        # write some entries to analytics.usercount with smallest interval as day
        stat = CountStat('test_messages_aggregate', zerver_count_message_by_user, {}, 'day', 'hour')

        # write some messages
        user1 = self.create_user('email1')
        user2 = self.create_user('email2')
        recipient = Recipient.objects.create(type_id=user2.id, type=Recipient.PERSONAL)

        self.create_message(user1, recipient)
        self.create_message(user1, recipient)
        self.create_message(user1, recipient)

        # run command
        self.process_last_hour(stat)

        # check no rows for hour interval on usercount granularity
        self.assertFalse(UserCount.objects.filter(realm=self.default_realm, interval='hour').exists())

        # see if aggregated correctly to realmcount and installationcount
        self.assertCountEquals(RealmCount, 'test_messages_aggregate', 3, interval = 'day')

        self.assertEquals(InstallationCount.objects.filter(interval='day',
                                                           property='test_messages_aggregate') \
                          .values_list('value', flat=True)[0], 3)

    def test_count_before_realm_creation(self):
        # type: () -> None
        stat = CountStat('test_active_humans', zerver_count_user_by_realm,
                         {'is_bot': False, 'is_active': True}, 'hour', 'hour')

        realm = Realm.objects.create(domain='domain', name='name', date_created=self.TIME_ZERO)
        self.create_user('email', realm=realm)

        # run count prior to realm creation
        process_count_stat(stat, range_start=self.TIME_ZERO - 2*self.HOUR,
                           range_end=self.TIME_LAST_HOUR)

        self.assertFalse(RealmCount.objects.filter(realm=realm).exists())

    def test_empty_counts_in_realm(self):
        # type: () -> None

        # test that rows with empty counts are returned if realm exists
        stat = CountStat('test_active_humans', zerver_count_user_by_realm,
                         {'is_bot': False, 'is_active': True}, 'hour', 'hour')

        self.create_user('email')

        process_count_stat(stat, range_start=self.TIME_ZERO - 2*self.HOUR,
                           range_end=self.TIME_ZERO)
        self.assertCountEquals(RealmCount, 'test_active_humans', 0, end_time = self.TIME_ZERO - 2*self.HOUR)
        self.assertCountEquals(RealmCount, 'test_active_humans', 0, end_time = self.TIME_LAST_HOUR)
        self.assertCountEquals(RealmCount, 'test_active_humans', 1, end_time = self.TIME_ZERO)

class TestAggregates(AnalyticsTestCase):
    pass

class TestXByYQueries(AnalyticsTestCase):
    def test_message_to_stream_aggregation(self):
        # type: () -> None
        stat = CountStat('test_messages_to_stream', zerver_count_message_by_stream, {}, 'hour', 'hour')

        # write some messages
        user = self.create_user('email')
        stream = self.create_stream(date_created=self.TIME_ZERO - 2*self.HOUR)

        recipient = Recipient(type_id=stream.id, type=Recipient.STREAM)
        recipient.save()

        self.create_message(user, recipient = recipient)

        # run command
        self.process_last_hour(stat)

        self.assertCountEquals(StreamCount, 'test_messages_to_stream', 1)

class TestCountStats(AnalyticsTestCase):
    def test_human_and_bot_count_by_realm(self):
        # type: () -> None
        stats = [
            CountStat('test_active_humans', zerver_count_user_by_realm, {'is_bot': False, 'is_active': True},
                      'hour', 'hour'),
            CountStat('test_active_bots', zerver_count_user_by_realm, {'is_bot': True, 'is_active': True},
                      'hour', 'hour')]

        # TODO these dates should probably be explicit, since the default args for the commands are timezone.now() dependent.
        self.create_user('email1-bot', is_bot=True)
        self.create_user('email2-bot', is_bot=True)
        self.create_user('email3-human', is_bot=False)

        for stat in stats:
            self.process_last_hour(stat)

        self.assertCountEquals(RealmCount, 'test_active_humans', 1)
        self.assertCountEquals(RealmCount, 'test_active_bots', 2)

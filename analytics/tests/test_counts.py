from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.test import TestCase

from datetime import datetime, timedelta
import pytz

from analytics.lib.interval import TimeInterval
from analytics.lib.counts import CountStat, process_count_stat, COUNT_STATS, \
    zerver_count_user_by_realm, zerver_count_message_by_user, \
    zerver_count_message_by_stream, zerver_count_stream_by_realm, \
    zerver_count_message_by_huddle
from analytics.models import UserCount, RealmCount, StreamCount, InstallationCount, Stream, Recipient

from zerver.lib.test_helpers import make_client, get_stream
from zerver.models import Realm, UserProfile, Message, get_user_profile_by_email

from typing import Any
from six import text_type

class AnalyticsTestCase(TestCase):
    MINUTE = timedelta(seconds = 60)
    HOUR = MINUTE * 60
    DAY = HOUR * 24
    TIME_ZERO = datetime(2042, 3, 14, tzinfo=pytz.UTC)
    TIME_LAST_HOUR = TIME_ZERO - HOUR

    default_realm = Realm.objects.get_or_create(domain='analytics.test', name='Realm Test',
                                         date_created=TIME_ZERO - 2*DAY)[0]

    # Lightweight creation of users, streams, and messages
    def create_user(self, email, **kwargs):
        # type: (str, **Any) -> UserProfile
        defaults = {'realm': self.default_realm,
                    'full_name': 'full_name',
                    'short_name': 'short_name',
                    'pointer': -1,
                    'last_pointer_updater': 'seems unused?',
                    'api_key': '42'}
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        return UserProfile.objects.create(email=email, **kwargs)

    def create_stream(self, **kwargs):
        # type: (**Any) -> Stream
        defaults = {'realm': self.default_realm,
                    'description': ''}
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        return Stream.objects.create(**kwargs)

    def create_message(self, sender, recipient, **kwargs):
        # type: (UserProfile, Recipient, **Any) -> Message
        sending_client = make_client(name="analytics test")
        defaults = {
            'sender': sender,
            'recipient': recipient,
            'subject': 'subject',
            'content': 'hello world',
            'pub_date': self.TIME_ZERO,
            'sending_client': sending_client,
            'last_edit_time': self.TIME_ZERO,
            'edit_history': '[]'
        }
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        return Message.objects.create(**kwargs)

    def process_last_hour(self, stat):
        # type: (CountStat) -> None
        process_count_stat(stat, self.TIME_ZERO, self.TIME_ZERO)

    # TODO: add end_time, make arguments optional?
    def assertRealmCountEquals(self, property, interval, value, realm = None):
        # type: (str, str, int, Optional[Realm]) -> None
        if realm is None:
            realm = self.default_realm
        realm_count_value = RealmCount.objects.filter(realm=realm,
                                                      property=property,
                                                      interval=interval) \
                                              .values_list('value', flat=True)[0]
        self.assertEqual(realm_count_value, value)

# Tests process_count_stat, manangement commands, backfilling, etc
class TestStatProcessing(AnalyticsTestCase):
    def setUp(self):
        # type: () -> None
        # many tests will need a realm and/or a user
        self.create_user(email='email')

    # test that process count does nothing if count already processed
    def test_process_count_stat(self):
        # type: () -> None
        # add some active and inactive users that are human
        self.create_user('inactive_human_1', is_bot=False, is_active=False,
                         date_joined=self.TIME_LAST_HOUR)
        self.create_user('inactive_human_2', is_bot=False, is_active=False,
                         date_joined=self.TIME_LAST_HOUR)
        self.create_user('active_human', is_bot=False, is_active=True,
                         date_joined=self.TIME_LAST_HOUR)

        # run stat to pull active humans
        stat = CountStat('active_humans', zerver_count_user_by_realm,
                         {'is_bot': False, 'is_active': True}, 'hour', 'hour')

        self.process_last_hour(stat)

        # get row in analytics table
        self.assertRealmCountEquals('active_humans', 'hour', 1)

        # run command again
        self.process_last_hour(stat)

        # check if row is same as before
        self.assertRealmCountEquals('active_humans', 'hour', 1)

    # test management commands
    def test_update_analytics_tables(self):
        # type: () -> None
        stat = CountStat('test_messages_sent', zerver_count_message_by_user, {}, 'hour', 'hour')

        human1 = self.create_user('human1', is_bot=False, is_active=True,
                                  date_joined=parse_datetime('2016-09-27 04:22:50+00:00'))

        human2 = get_user_profile_by_email('email')

        self.create_message(human1, Recipient(human2.id),
                            pub_date=parse_datetime('2016-09-27 04:30:50+00:00'))

        # run command
        process_count_stat(stat, range_start=parse_datetime('2016-09-27 04:00:50+00:00'),
                           range_end=parse_datetime('2016-09-27 05:00:50+00:00'))
        usercount_row = UserCount.objects.filter(realm=self.default_realm, interval='hour',
                                                 property='test_messages_sent').values_list(
            'value', flat=True)[0]
        assert (usercount_row == 1)

        # run command with dates before message creation
        process_count_stat(stat, range_start=parse_datetime('2016-09-27 01:00:50+00:00'),
                           range_end=parse_datetime('2016-09-22 02:00:50+00:00'))

        # check new row has no entries, old ones still there
        updated_usercount_row = UserCount.objects.filter(
            realm=self.default_realm, interval='hour', property='test_messages_sent') \
                                                 .values_list('value', flat=True)[0]

        new_row = UserCount.objects.filter(realm=self.default_realm, interval='hour', property='test_messages_sent',
            end_time=datetime(2016, 9, 22, 5, 0).replace(tzinfo=timezone.utc)).exists()

        self.assertFalse(new_row)

        assert (updated_usercount_row == 1)


class TestAggregates(AnalyticsTestCase):
    def test_do_aggregate(self):
        # type: () -> None

        # write some entries to analytics.usercount with smallest interval as day
        stat = CountStat('test_messages_aggregate', zerver_count_message_by_user, {}, 'day', 'hour')

        self.create_user(email='email')

        # write some messages
        self.create_user('human1', is_bot=False, is_active=True,
                         date_joined=parse_datetime('2016-09-27 04:22:50+00:00'))

        human1 = get_user_profile_by_email('human1')
        human2 = get_user_profile_by_email('email')

        self.create_message(human1, Recipient(human2.id),
                            pub_date=parse_datetime('2016-09-27 04:30:50+00:00'),
                            content="hi")
        self.create_message(human1, Recipient(human2.id),
                            pub_date=parse_datetime('2016-09-27 04:30:50+00:00'),
                            content="hello")
        self.create_message(human1, Recipient(human2.id),
                            pub_date=parse_datetime('2016-09-27 04:30:50+00:00'),
                            content="bye")

        # run command
        process_count_stat(stat, range_start=parse_datetime('2016-09-27 04:00:50+00:00'),
                           range_end=parse_datetime('2016-09-27 05:00:50+00:00'))

        # check no rows for hour interval on usercount granularity
        usercount_row = UserCount.objects.filter(realm=self.default_realm, interval='hour').exists()

        self.assertFalse(usercount_row)

        # see if aggregated correctly to realmcount and installationcount
        realmcount_row = RealmCount.objects.filter(realm=self.default_realm, interval='day',
                                                   property='test_messages_aggregate').values_list(
            'value', flat=True)[0]
        assert (realmcount_row == 3)

        installationcount_row = InstallationCount.objects.filter(interval='day',
                                                                 property='test_messages_aggregate') \
                                                         .values_list('value', flat=True)[0]
        assert (installationcount_row == 3)

class TestCountXByYQueries(AnalyticsTestCase):
    # each test here should test for the non-zero case, the zero case, and
    # the empty case, to make sure all the joins were done correctly.
    def test_count_message_by_stream(self):
        # type: () -> None
        stat = CountStat('test_messages_to_stream', zerver_count_message_by_stream, {}, 'hour', 'hour')

        # write some messages
        user = self.create_user(email='email')

        self.create_stream(name='stream1', description='test_analytics_stream',
                           date_created=parse_datetime('2016-09-27 03:10:50+00:00'))

        stream1 = get_stream('stream1', self.default_realm)
        recipient = Recipient(type_id=stream1.id, type=2)
        recipient.save()

        self.create_message(user, recipient, pub_date=parse_datetime('2016-09-27 04:30:50+00:00'),
                            content='hi')

        # run command
        process_count_stat(stat, range_start=parse_datetime('2016-09-27 04:00:50+00:00'),
                           range_end=parse_datetime('2016-09-27 05:00:50+00:00'))

        stream_row = StreamCount.objects.filter(realm=self.default_realm, interval='hour',
                                                property='test_messages_to_stream').values_list(
            'value', flat=True)[0]
        assert (stream_row == 1)

    def test_count_user_by_realm(self):
        # type: () -> None

        # test that rows with empty counts are returned if realm exists
        stat = CountStat('test_active_humans', zerver_count_user_by_realm,
                         {'is_bot': False, 'is_active': True}, 'hour', 'hour')

        self.create_user('human1', is_bot=False, is_active=True,
                         date_joined=self.TIME_ZERO)

        process_count_stat(stat, range_start=self.TIME_ZERO - 2*self.HOUR,
                           range_end=self.TIME_ZERO + 2*self.HOUR)
        realm_count = RealmCount.objects.values('end_time', 'value') \
                                        .filter(realm=self.default_realm, interval='hour')

        empty1 = realm_count.filter(end_time=self.TIME_ZERO - self.HOUR) \
                            .values_list('value', flat=True)[0]
        empty2 = realm_count.filter(end_time=self.TIME_ZERO + 2*self.HOUR) \
                            .values_list('value', flat=True)[0]
        nonempty = realm_count.filter(end_time=self.TIME_ZERO + self.HOUR) \
                              .values_list('value', flat=True)[0]
        assert (empty1 == 0)
        assert (empty2 == 0)
        assert (nonempty == 1)

    # is also a count_user_by_realm test
    def test_count_before_realm_creation(self):
        # type: () -> None
        stat = CountStat('test_active_humans', zerver_count_user_by_realm,
                         {'is_bot': False, 'is_active': True}, 'hour', 'hour')

        self.default_realm.date_created = parse_datetime('2016-09-30 01:00:50+00:00')
        self.default_realm.save()
        self.create_user('human1', is_bot=False, is_active=True,
                         date_joined=parse_datetime('2016-09-30 04:22:50+00:00'))

        # run count prior to realm creation
        process_count_stat(stat, range_start=parse_datetime('2016-09-26 04:00:50+00:00'),
                           range_end=parse_datetime('2016-09-26 05:00:50+00:00'))
        realm_count = RealmCount.objects.values('realm__name', 'value', 'property') \
                                        .filter(realm=self.default_realm, interval='hour').exists()
        # assert no rows exist
        self.assertFalse(realm_count)


class TestCountStats(AnalyticsTestCase):
    def test_active_humans_and_active_bots(self):
        # type: () -> None
        self.create_user('test_bot1', is_bot=True)
        self.create_user('test_bot2', is_bot=True)
        self.create_user('test_human', is_bot=False)

        self.process_last_hour(COUNT_STATS['active_humans'])
        self.process_last_hour(COUNT_STATS['active_bots'])

        self.assertRealmCountEquals('active_humans', 'gauge', 1)
        self.assertRealmCountEquals('active_bots', 'gauge', 2)

    def test_messages_sent(self):
        # type: () -> None
        pass

    # test users added in last hour --> test_new_humans, or similar
    def test_add_new_users(self):
        # type: () -> None
        stat = CountStat('add_new_user_test', zerver_count_user_by_realm, {}, 'hour', 'hour')

        # add new users to realm in last hour
        self.create_user('email_1', date_joined=self.TIME_ZERO - self.MINUTE) # doesn't work without the -self.MINUTE ??
        self.create_user('email_2', date_joined=self.TIME_ZERO - self.MINUTE)

        # add a new user before an hour
        self.create_user('email_3', date_joined=self.TIME_ZERO - 61*self.MINUTE)

        # check if user added before the hour is not included
        self.process_last_hour(stat)
        # do_update is writing the stat.property to all zerver tables
        self.assertRealmCountEquals('add_new_user_test', 'hour', 2)

    # rename
    def test_analytics_stat_write(self):
        # type: () -> None
        # might change if we refactor count_query

        stat = CountStat('test_stat_write', zerver_count_stream_by_realm,
                         {'invite_only': False}, 'hour', 'hour')

        # add some stuff to zerver_*
        self.create_stream(name='stream1', description='test_analytics_stream',
                           date_created=parse_datetime('2016-09-27 02:10:50+00:00'))
        self.create_stream(name='stream2', description='test_analytics_stream',
                           date_created=parse_datetime('2016-09-27 02:10:50+00:00'))
        self.create_stream(name='stream3', description='test_analytics_stream',
                           date_created=parse_datetime('2016-09-27 02:10:50+00:00'))

        # run do_pull_from_zerver
        self.process_last_hour(stat)

        # check analytics_* values are correct
        self.assertRealmCountEquals('test_stat_write', 'day', 3)

## Cleanup TODO
# replace all times with TIME_ZERO
# remove create_user from setUp
# remove unneeded fields in object creation (e.g. description from create_stream)
# rename human to user when it is not important that it is a humans
# add end_time to assertRealmCountEquals, and allow arguments to be None
# write assertUserCountEquals, assertStreamCountEquals (or maybe assertCountEquals, for both)

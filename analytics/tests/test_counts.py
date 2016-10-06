from django.utils import timezone
from django.test import TestCase

from datetime import datetime, timedelta

from analytics.lib.interval import TimeInterval
from analytics.lib.counts import CountStat, process_count_stat, \
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
    TIME_ZERO = datetime(2042, 3, 14).replace(tzinfo=timezone.utc)
    TIME_LAST_HOUR = TIME_ZERO - HOUR

    def process_last_hour(self, stat):
        # type: (CountStat) -> None
        # The last two arguments below are eventually passed as the first and
        # last arguments of lib.interval.timeinterval_range, which is an
        # inclusive range.
        process_count_stat(stat, self.TIME_ZERO, self.TIME_ZERO)

class TestDataCollectors(AnalyticsTestCase):
    def create_user(self, email, **kwargs):
        # type: (str, **Any) -> UserProfile
        defaults = {'realm': self.realm,
                    'full_name': 'full_name',
                    'short_name': 'short_name',
                    'pointer': -1,
                    'last_pointer_updater': 'seems unused?',
                    'api_key': '42'}
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        user = UserProfile(email=email, **kwargs)
        user.save()
        return user

    def create_stream(self, **kwargs):
        # type: (**Any) -> Stream
        defaults = {'realm': self.realm,
                    'description': ''}
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        stream = Stream(**kwargs)
        stream.save()
        return stream

    def create_message(self, sender, recipient, **kwargs):
        # type: (UserProfile, Recipient, **Any) -> Message
        sending_client = make_client(name="analytics test")
        defaults = {
            'sender': sender,
            'recipient': recipient,
            'subject': 'whatever',
            'content': 'hello **world**',
            'pub_date': self.TIME_ZERO,
            'sending_client': sending_client,
            'last_edit_time': self.TIME_ZERO,
            'edit_history': '[]'
        }
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        message = Message(**kwargs)
        message.save()
        return message

    # TODO uk refactor tests to use this assert
    def assertRealmCountEquals(self, realm, property, interval, value):
        # type: (Realm, str, str, Any) -> None
        realm_count_value = RealmCount.objects.filter(realm=realm,
                                                      property=property,
                                                      interval=interval).values_list('value', flat=True)[0]

        self.assertEqual(realm_count_value, value)

    def setUp(self):
        # type: () -> None
        # almost every test will need a time_interval, realm, and user
        self.realm = Realm(domain='analytics.test', name='Realm Test',
                           date_created=self.TIME_ZERO - 2*self.DAY)
        self.realm.save()
        # don't pull the realm object back from the database every time we need its id
        self.realm_id = self.realm.id
        self.user = self.create_user('email', is_bot=False, is_active=True,
                                     date_joined=self.TIME_ZERO)
        self.user_id = self.user.id

    def test_human_and_bot_count_by_realm(self):
        # type: () -> None

        stats = [
            CountStat('test_active_humans', zerver_count_user_by_realm, {'is_bot': False, 'is_active': True},
                      'hour', 'hour'),
            CountStat('test_active_bots', zerver_count_user_by_realm, {'is_bot': True, 'is_active': True},
                      'hour', 'hour')]

        # TODO these dates should probably be explicit, since the default args for the commands are timezone.now() dependent.
        self.create_user('test_bot1', is_bot=True, is_active=True,
                         date_joined=self.TIME_LAST_HOUR)
        self.create_user('test_bot2', is_bot=True, is_active=True,
                         date_joined=self.TIME_LAST_HOUR)
        self.create_user('test_human', is_bot=False, is_active=True,
                         date_joined=self.TIME_LAST_HOUR)

        for stat in stats:
            self.process_last_hour(stat)

        human_row = RealmCount.objects.filter(realm=self.realm, interval='day',
                                              property='test_active_humans') \
                                      .values_list('value', flat=True)[0]
        assert (human_row == 1)

        bot_row = RealmCount.objects.filter(realm=self.realm, interval='day',
                                            property='test_active_bots') \
                                    .values_list('value', flat=True)[0]
        assert (bot_row == 2)

    # test users added in last hour
    def test_add_new_users(self):
        # type: () -> None
        stat = CountStat('add_new_user_test', zerver_count_user_by_realm, {}, 'hour', 'hour')

        # add new users to realm in last hour
        self.create_user('email_1', date_joined=self.TIME_LAST_HOUR)
        self.create_user('email_2', date_joined=self.TIME_LAST_HOUR)

        # add a new user before an hour
        self.create_user('email_3', date_joined=self.TIME_ZERO - 2*self.HOUR)

        # check if user added before the hour is not included
        self.process_last_hour(stat)
        # do_update is writing the stat.property to all zerver tables
        row = RealmCount.objects.filter(realm=self.realm, property='add_new_user_test',
                                        interval='hour').values_list('value', flat=True)[0]
        # assert only 2 users
        assert (row == 2)

    def test_analytics_stat_write(self):
        # type: () -> None
        # might change if we refactor count_query

        stat = CountStat('test_stat_write', zerver_count_stream_by_realm,
                         {'invite_only': False}, 'hour', 'hour')

        # add some stuff to zerver_*
        self.create_stream(name='stream1', description='test_analytics_stream',
                           date_created=self.TIME_ZERO)
        self.create_stream(name='stream2', description='test_analytics_stream',
                           date_created=self.TIME_ZERO)
        self.create_stream(name='stream3', description='test_analytics_stream',
                           date_created=self.TIME_ZERO)

        # run do_pull_from_zerver
        self.process_last_hour(stat)

        # check analytics_* values are correct
        row = RealmCount.objects.filter(realm=self.realm, interval='day',
                                        property='test_stat_write').values_list('value', flat=True)[0]
        assert (row == 3)

    # test if process count does nothing if count already processed
    def test_process_count(self):
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
        row_before = RealmCount.objects.filter(realm=self.realm, interval='day',
                                               property='active_humans')\
                                       .values_list('value', flat=True)[0]

        # run command again
        self.process_last_hour(stat)

        # check if row is same as before
        row_after = RealmCount.objects.filter(realm=self.realm, interval='day',
                                              property='active_humans').values_list('value', flat=True)[0]

        assert (row_before == 1)
        assert (row_before == row_after)

    # test management commands
    def test_update_analytics_tables(self):
        # type: () -> None
        stat = CountStat('test_messages_sent', zerver_count_message_by_user, {}, 'hour', 'hour')

        self.create_user('human1', is_bot=False, is_active=True,
                         date_joined=self.TIME_LAST_HOUR)

        human1 = get_user_profile_by_email('human1')
        human2 = get_user_profile_by_email('email')

        self.create_message(human1, Recipient(human2.id),
                            pub_date=self.TIME_LAST_HOUR)

        # run command
        self.process_last_hour(stat)
        usercount_row = UserCount.objects.filter(realm=self.realm, interval='hour',
                                                 property='test_messages_sent').values_list(
            'value', flat=True)[0]
        assert (usercount_row == 1)

        # run command with dates before message creation
        process_count_stat(stat, range_start=self.TIME_ZERO - 2*self.HOUR,
                           range_end=self.TIME_LAST_HOUR)

        # check new row has no entries, old ones still there
        updated_usercount_row = UserCount.objects.filter(
            realm=self.realm, interval='hour', property='test_messages_sent') \
                                                 .values_list('value', flat=True)[0]

        new_row = UserCount.objects.filter(realm=self.realm, interval='hour', property='test_messages_sent',
                                           end_time=self.TIME_ZERO - 3*self.HOUR).exists()

        self.assertFalse(new_row)

        assert (updated_usercount_row == 1)

    def test_do_aggregate(self):
        # type: () -> None

        # write some entries to analytics.usercount with smallest interval as day
        stat = CountStat('test_messages_aggregate', zerver_count_message_by_user, {}, 'day', 'hour')

        # write some messages
        self.create_user('human1', is_bot=False, is_active=True,
                         date_joined=self.TIME_LAST_HOUR)

        human1 = get_user_profile_by_email('human1')
        human2 = get_user_profile_by_email('email')

        self.create_message(human1, Recipient(human2.id),
                            pub_date=self.TIME_LAST_HOUR,
                            content="hi")
        self.create_message(human1, Recipient(human2.id),
                            pub_date=self.TIME_LAST_HOUR,
                            content="hello")
        self.create_message(human1, Recipient(human2.id),
                            pub_date=self.TIME_LAST_HOUR,
                            content="bye")

        # run command
        self.process_last_hour(stat)

        # check no rows for hour interval on usercount granularity
        usercount_row = UserCount.objects.filter(realm=self.realm, interval='hour').exists()

        self.assertFalse(usercount_row)

        # see if aggregated correctly to realmcount and installationcount
        realmcount_row = RealmCount.objects.filter(realm=self.realm, interval='day',
                                                   property='test_messages_aggregate').values_list(
            'value', flat=True)[0]
        assert (realmcount_row == 3)

        installationcount_row = InstallationCount.objects.filter(interval='day',
                                                                 property='test_messages_aggregate') \
                                                         .values_list('value', flat=True)[0]
        assert (installationcount_row == 3)

    def test_message_to_stream_aggregation(self):
        # type: () -> None
        stat = CountStat('test_messages_to_stream', zerver_count_message_by_stream, {}, 'hour', 'hour')

        # write some messages
        user = get_user_profile_by_email('email')

        self.create_stream(name='stream1', description='test_analytics_stream',
                           date_created=self.TIME_ZERO - 2*self.HOUR)

        stream1 = get_stream('stream1', self.realm)
        recipient = Recipient(type_id=stream1.id, type=2)
        recipient.save()

        self.create_message(user, recipient, pub_date=self.TIME_LAST_HOUR,
                            content='hi')

        # run command
        self.process_last_hour(stat)

        stream_row = StreamCount.objects.filter(realm=self.realm, interval='hour',
                                                property='test_messages_to_stream').values_list(
            'value', flat=True)[0]
        assert (stream_row == 1)

    def test_count_before_realm_creation(self):
        # type: () -> None
        stat = CountStat('test_active_humans', zerver_count_user_by_realm,
                         {'is_bot': False, 'is_active': True}, 'hour', 'hour')

        self.realm.date_created = self.TIME_ZERO
        self.realm.save()
        self.create_user('human1', is_bot=False, is_active=True,
                         date_joined=self.TIME_ZERO)

        # run count prior to realm creation
        process_count_stat(stat, range_start=self.TIME_ZERO - 2*self.HOUR,
                           range_end=self.TIME_LAST_HOUR)
        realm_count = RealmCount.objects.values('realm__name', 'value', 'property') \
                                        .filter(realm=self.realm, interval='hour').exists()
        # assert no rows exist
        self.assertFalse(realm_count)

    def test_empty_counts_in_realm(self):
        # type: () -> None

        # test that rows with empty counts are returned if realm exists
        stat = CountStat('test_active_humans', zerver_count_user_by_realm,
                         {'is_bot': False, 'is_active': True}, 'hour', 'hour')

        self.create_user('human1', is_bot=False, is_active=True,
                         date_joined=self.TIME_LAST_HOUR)

        process_count_stat(stat, range_start=self.TIME_ZERO - 2*self.HOUR,
                           range_end=self.TIME_ZERO)
        realm_count = RealmCount.objects.values('end_time', 'value') \
                                        .filter(realm=self.realm, interval='hour')
        empty1 = realm_count.filter(end_time=self.TIME_ZERO - 2*self.HOUR) \
                            .values_list('value', flat=True)[0]
        empty2 = realm_count.filter(end_time=self.TIME_LAST_HOUR) \
                            .values_list('value', flat=True)[0]
        nonempty = realm_count.filter(end_time=self.TIME_ZERO) \
                              .values_list('value', flat=True)[0]
        assert (empty1 == 0)
        assert (empty2 == 0)
        assert (nonempty == 1)

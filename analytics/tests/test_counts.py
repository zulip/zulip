from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.test import TestCase

from datetime import datetime, timedelta

from analytics.lib.counts import CountStat
from analytics.lib.interval import TimeInterval
from analytics.lib.counts import process_count_stat
from analytics.models import UserCount, RealmCount, StreamCount, InstallationCount, Stream, Recipient

from zerver.lib.test_helpers import make_client, get_stream
from zerver.models import Realm, UserProfile, Message, get_user_profile_by_email

from typing import Any
from six import text_type


def do_update_past_hour(stat):
    # type: (CountStat) -> Any
    return process_count_stat(stat, range_start=timezone.now() - timedelta(seconds=3600),
                              range_end=timezone.now())


class TestDataCollectors(TestCase):
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
            'pub_date': timezone.now(),
            'sending_client': sending_client,
            'last_edit_time': timezone.now(),
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
        end = timezone.now() + timedelta(seconds=7200)
        self.day_interval = TimeInterval('day', end, 'hour')
        self.hour_interval = TimeInterval('hour', end, 'hour')
        self.realm = Realm(domain='analytics.test', name='Realm Test',
                           date_created=parse_datetime('2016-09-27 01:00:50+00:00'))
        self.realm.save()
        # don't pull the realm object back from the database every time we need its id
        self.realm_id = self.realm.id
        self.user = self.create_user('email', is_bot=False, is_active=True,
                                     date_joined=parse_datetime('2016-09-27 04:20:50+00:00'))
        self.user_id = self.user.id

    def test_human_and_bot_count_by_realm(self):
        # type: () -> None

        stats = [

            CountStat('test_active_humans', UserProfile, {'is_bot': False, 'is_active': True},
                      RealmCount, 'hour', 'hour'),
            CountStat('test_active_bots', UserProfile, {'is_bot': True, 'is_active': True},
                      RealmCount, 'hour', 'hour')
        ]

        # TODO these dates should probably be explicit, since the default args for the commands are timezone.now() dependent.
        self.create_user('test_bot1', is_bot=True, is_active=True,
                         date_joined=timezone.now() - timedelta(hours=1))
        self.create_user('test_bot2', is_bot=True, is_active=True,
                         date_joined=timezone.now() - timedelta(hours=1))
        self.create_user('test_human', is_bot=False, is_active=True,
                         date_joined=timezone.now() - timedelta(hours=1))

        for stat in stats:
            do_update_past_hour(stat)

        human_row = RealmCount.objects.filter(realm=self.realm, interval='day',
                                              property='test_active_humans').values_list('value', flat=True)[0]
        assert (human_row == 1)

        bot_row = RealmCount.objects.filter(realm=self.realm, interval='day',
                                            property='test_active_bots').values_list('value', flat=True)[0]
        assert (bot_row == 2)

    # test users added in last hour
    def test_add_new_users(self):
        # type: () -> None
        stat = CountStat('add_new_user_test', UserProfile, {},
                         RealmCount, 'hour', 'hour')

        # add new users to realm in last hour
        self.create_user('email_1', date_joined=parse_datetime('2016-09-27 03:22:50+00:00'))
        self.create_user('email_2', date_joined=parse_datetime('2016-09-27 03:15:50+00:00'))

        # add a new user before an hour
        self.create_user('email_3', date_joined=parse_datetime('2016-09-27 02:10:50+00:00'))

        # check if user added before the hour is not included
        process_count_stat(stat, range_start=parse_datetime('2016-09-27 03:00:50+00:00'),
                           range_end=parse_datetime('2016-09-27 04:00:50+00:00'))
        # do_update is writing the stat.property to all zerver tables
        row = RealmCount.objects.filter(realm=self.realm, property='add_new_user_test',
                                        interval='hour').values_list('value', flat=True)[0]
        # assert only 2 users
        assert (row == 2)

    def test_analytics_stat_write(self):
        # type: () -> None
        # might change if we refactor count_query

        stat = CountStat('test_stat_write', Stream, {'invite_only': False}, RealmCount, 'hour', 'hour')

        # add some stuff to zerver_*
        self.create_stream(name='stream1', description='test_analytics_stream',
                           date_created=parse_datetime('2016-09-27 02:10:50+00:00'))
        self.create_stream(name='stream2', description='test_analytics_stream',
                           date_created=parse_datetime('2016-09-27 02:10:50+00:00'))
        self.create_stream(name='stream3', description='test_analytics_stream',
                           date_created=parse_datetime('2016-09-27 02:10:50+00:00'))

        # run do_pull_from_zerver
        do_update_past_hour(stat)

        # check analytics_* values are correct
        row = RealmCount.objects.filter(realm=self.realm, interval='day',
                                        property='test_stat_write').values_list('value', flat=True)[0]
        assert (row == 3)

    # test if process count does nothing if count already processed
    def test_process_count(self):
        # type: () -> None
        # add some active and inactive users that are human
        self.create_user('inactive_human_1', is_bot=False, is_active=False,
                         date_joined=timezone.now() - timedelta(hours=1))
        self.create_user('inactive_human_2', is_bot=False, is_active=False,
                         date_joined=timezone.now() - timedelta(hours=1))
        self.create_user('active_human', is_bot=False, is_active=True,
                         date_joined=timezone.now() - timedelta(hours=1))

        # run stat to pull active humans
        stat = CountStat('active_humans', UserProfile, {'is_bot': False, 'is_active': True},
                         RealmCount, 'hour', 'hour')

        do_update_past_hour(stat)

        # get row in analytics table
        row_before = RealmCount.objects.filter(realm=self.realm, interval='day',
                                               property='active_humans').values_list('value', flat=True)[0]

        # run command again
        do_update_past_hour(stat)

        # check if row is same as before
        row_after = RealmCount.objects.filter(realm=self.realm, interval='day',
                                              property='active_humans').values_list('value', flat=True)[0]

        assert (row_before == 1)
        assert (row_before == row_after)

    # test management commands
    def test_update_analytics_tables(self):
        # type: () -> None
        stat = CountStat('test_messages_sent', Message, {},
                         UserCount, 'hour', 'hour')

        self.create_user('human1', is_bot=False, is_active=True,
                         date_joined=parse_datetime('2016-09-27 04:22:50+00:00'))

        human1 = get_user_profile_by_email('human1')
        human2 = get_user_profile_by_email('email')

        self.create_message(human1, Recipient(human2.id), pub_date=parse_datetime('2016-09-27 04:30:50+00:00'))

        # run command
        process_count_stat(stat, range_start=parse_datetime('2016-09-27 04:00:50+00:00'),
                           range_end=parse_datetime('2016-09-27 05:00:50+00:00'))
        usercount_row = UserCount.objects.filter(realm=self.realm, interval='hour',
                                                 property='test_messages_sent').values_list(
            'value', flat=True)[0]
        assert (usercount_row == 1)

        # run command with dates before message creation
        process_count_stat(stat, range_start=parse_datetime('2016-09-27 01:00:50+00:00'),
                           range_end=parse_datetime('2016-09-22 02:00:50+00:00'))

        # check new row has no entries, old ones still there
        updated_usercount_row = UserCount.objects.filter(
            realm=self.realm, interval='hour', property='test_messages_sent').values_list('value', flat=True)[0]

        new_row = UserCount.objects.filter(realm=self.realm, interval='hour', property='test_messages_sent',
            end_time=datetime(2016, 9, 22, 5, 0).replace(tzinfo=timezone.utc)).exists()

        self.assertFalse(new_row)

        assert (updated_usercount_row == 1)

    def test_do_aggregate(self):
        # type: () -> None

        # write some entries to analytics.usercount with smallest interval as day
        stat = CountStat('test_messages_aggregate', Message, {},
                         UserCount, 'day', 'hour')

        # write some messages
        self.create_user('human1', is_bot=False, is_active=True,
                         date_joined=parse_datetime('2016-09-27 04:22:50+00:00'))

        human1 = get_user_profile_by_email('human1')
        human2 = get_user_profile_by_email('email')

        self.create_message(human1, Recipient(human2.id),
                            pub_date=parse_datetime('2016-09-27 04:30:50+00:00'), content="hi")
        self.create_message(human1, Recipient(human2.id),
                            pub_date=parse_datetime('2016-09-27 04:30:50+00:00'), content="hello")
        self.create_message(human1, Recipient(human2.id),
                            pub_date=parse_datetime('2016-09-27 04:30:50+00:00'), content="bye")

        # run command
        process_count_stat(stat, range_start=parse_datetime('2016-09-27 04:00:50+00:00'),
                           range_end=parse_datetime('2016-09-27 05:00:50+00:00'))

        # check no rows for hour interval on usercount granularity
        usercount_row = UserCount.objects.filter(realm=self.realm, interval='hour').exists()

        self.assertFalse(usercount_row)

        # see if aggregated correctly to realmcount and installationcount
        realmcount_row = RealmCount.objects.filter(realm=self.realm, interval='day',
                                                   property='test_messages_aggregate').values_list(
            'value', flat=True)[0]
        assert (realmcount_row == 3)

        installationcount_row = InstallationCount.objects.filter(interval='day',
                                                                 property='test_messages_aggregate').values_list(
            'value', flat=True)[0]
        assert (installationcount_row == 3)

    def test_message_to_stream_aggregation(self):
        # type: () -> None
        stat = CountStat('test_messages_to_stream', Message, {},
                         StreamCount, 'hour', 'hour')

        # write some messages
        user = get_user_profile_by_email('email')

        self.create_stream(name='stream1', description='test_analytics_stream',
                           date_created=parse_datetime('2016-09-27 03:10:50+00:00'))

        stream1 = get_stream('stream1', self.realm)
        recipient = Recipient(type_id=stream1.id, type=2)
        recipient.save()

        self.create_message(user, recipient, pub_date=parse_datetime('2016-09-27 04:30:50+00:00'), content='hi')

        # run command
        process_count_stat(stat, range_start=parse_datetime('2016-09-27 04:00:50+00:00'),
                           range_end=parse_datetime('2016-09-27 05:00:50+00:00'))

        stream_row = StreamCount.objects.filter(realm=self.realm, interval='hour',
                                                property='test_messages_to_stream').values_list(
            'value', flat=True)[0]
        assert (stream_row == 1)

    def test_count_before_realm_creation(self):
        # type: () -> None
        stat = CountStat('test_active_humans', UserProfile, {'is_bot': False, 'is_active': True},
                         RealmCount, 'hour', 'hour')

        self.realm.date_created = parse_datetime('2016-09-30 01:00:50+00:00')
        self.realm.save()
        self.create_user('human1', is_bot=False, is_active=True,
                         date_joined=parse_datetime('2016-09-30 04:22:50+00:00'))

        # run count prior to realm creation
        process_count_stat(stat, range_start=parse_datetime('2016-09-26 04:00:50+00:00'),
                           range_end=parse_datetime('2016-09-26 05:00:50+00:00'))
        realm_count = RealmCount.objects.values('realm__name', 'value', 'property').filter(realm=self.realm,
                                                                                           interval='hour').exists()
        # assert no rows exist
        self.assertFalse(realm_count)

    def test_empty_counts_in_realm(self):
        # type: () -> None

        # test that rows with empty counts are returned if realm exists
        stat = CountStat('test_active_humans', UserProfile, {'is_bot': False, 'is_active': True},
                         RealmCount, 'hour', 'hour')

        self.create_user('human1', is_bot=False, is_active=True,
                         date_joined=parse_datetime('2016-09-27 02:22:50+00:00'))

        process_count_stat(stat, range_start=parse_datetime('2016-09-27 01:00:50+00:00'),
                           range_end=parse_datetime('2016-09-27 05:00:50+00:00'))
        realm_count = RealmCount.objects.values('end_time', 'value').filter(realm=self.realm, interval='hour')
        empty1 = realm_count.filter(end_time=datetime(2016, 9, 27, 2, 0,
                                                      tzinfo=timezone.utc)).values_list('value', flat=True)[0]
        empty2 = realm_count.filter(end_time=datetime(2016, 9, 27, 4, 0,
                                                      tzinfo=timezone.utc)).values_list('value', flat=True)[0]
        nonempty = realm_count.filter(end_time=datetime(2016, 9, 27, 5, 0,
                                                        tzinfo=timezone.utc)).values_list('value', flat=True)[0]
        assert (empty1 == 0)
        assert (empty2 == 0)
        assert (nonempty == 1)

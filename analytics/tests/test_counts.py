from __future__ import absolute_import

from django.db import models
from django.test import TestCase
from django.utils import timezone

from analytics.lib.counts import CountStat, COUNT_STATS, process_count_stat, \
    zerver_count_user_by_realm, zerver_count_message_by_user, \
    zerver_count_message_by_stream, zerver_count_stream_by_realm, \
    do_fill_count_stat_at_hour, ZerverCountQuery
from analytics.models import BaseCount, InstallationCount, RealmCount, \
    UserCount, StreamCount, FillState, installation_epoch
from zerver.models import Realm, UserProfile, Message, Stream, Recipient, \
    Huddle, Client, get_user_profile_by_email, get_client

from datetime import datetime, timedelta

from six.moves import range
from typing import Any, Type, Optional, Text, Tuple, List, Union

class AnalyticsTestCase(TestCase):
    MINUTE = timedelta(seconds = 60)
    HOUR = MINUTE * 60
    DAY = HOUR * 24
    TIME_ZERO = datetime(1988, 3, 14).replace(tzinfo=timezone.utc)
    TIME_LAST_HOUR = TIME_ZERO - HOUR

    def setUp(self):
        # type: () -> None
        self.default_realm = Realm.objects.create(
            string_id='realmtest', name='Realm Test',
            domain='test.analytics', date_created=self.TIME_ZERO - 2*self.DAY)
        # used to generate unique names in self.create_*
        self.name_counter = 100
        # used as defaults in self.assertCountEquals
        self.current_property = None # type: Optional[str]

    # Lightweight creation of users, streams, and messages
    def create_user(self, **kwargs):
        # type: (**Any) -> UserProfile
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

    def create_stream_with_recipient(self, **kwargs):
        # type: (**Any) -> Tuple[Stream, Recipient]
        self.name_counter += 1
        defaults = {'name': 'stream name %s' % (self.name_counter,),
                    'realm': self.default_realm,
                    'date_created': self.TIME_LAST_HOUR}
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        stream = Stream.objects.create(**kwargs)
        recipient = Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)
        return stream, recipient

    def create_huddle_with_recipient(self, **kwargs):
        # type: (**Any) -> Tuple[Huddle, Recipient]
        self.name_counter += 1
        defaults = {'huddle_hash': 'hash%s' % (self.name_counter,)}
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        huddle = Huddle.objects.create(**kwargs)
        recipient = Recipient.objects.create(type_id=huddle.id, type=Recipient.HUDDLE)
        return huddle, recipient

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

    # kwargs should only ever be a UserProfile or Stream.
    def assertCountEquals(self, table, value, property=None, subgroup=None,
                          end_time=TIME_ZERO, realm=None, **kwargs):
        # type: (Type[BaseCount], int, Optional[Text], Optional[Text], datetime, Optional[Realm], **models.Model) -> None
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

    def assertTableState(self, table, arg_keys, arg_values):
        # type: (Type[BaseCount], List[str], List[List[Union[int, str, Realm, UserProfile, Stream]]]) -> None
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
            'end_time': self.TIME_ZERO}
        for values in arg_values:
            kwargs = {} # type: Dict[str, Any]
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
    def make_dummy_count_stat(self, current_time):
        # type: (datetime) -> CountStat
        dummy_query = """INSERT INTO analytics_realmcount (realm_id, property, end_time, value)
                                VALUES (1, 'test stat', '%(end_time)s', 22)""" % {'end_time': current_time}
        stat = CountStat('test stat', ZerverCountQuery(Recipient, UserCount, dummy_query),
                         {}, None, CountStat.HOUR, False)
        return stat

    def assertFillStateEquals(self, end_time, state=FillState.DONE, property=None):
        # type: (datetime, int, Optional[Text]) -> None
        stat = self.make_dummy_count_stat(end_time)
        if property is None:
            property = stat.property
        fill_state = FillState.objects.filter(property=property).first()
        self.assertEqual(fill_state.end_time, end_time)
        self.assertEqual(fill_state.state, state)

    def test_process_stat(self):
        # type: () -> None
        # process new stat
        current_time = installation_epoch() + self.HOUR
        stat = self.make_dummy_count_stat(current_time)
        property = stat.property
        process_count_stat(stat, current_time)
        self.assertFillStateEquals(current_time)
        self.assertEqual(InstallationCount.objects.filter(property=property).count(), 1)

        # dirty stat
        FillState.objects.filter(property=property).update(state=FillState.STARTED)
        process_count_stat(stat, current_time)
        self.assertFillStateEquals(current_time)
        self.assertEqual(InstallationCount.objects.filter(property=property).count(), 1)

        # clean stat, no update
        process_count_stat(stat, current_time)
        self.assertFillStateEquals(current_time)
        self.assertEqual(InstallationCount.objects.filter(property=property).count(), 1)

        # clean stat, with update
        current_time = current_time + self.HOUR
        stat = self.make_dummy_count_stat(current_time)
        process_count_stat(stat, current_time)
        self.assertFillStateEquals(current_time)
        self.assertEqual(InstallationCount.objects.filter(property=property).count(), 2)

class TestCountStats(AnalyticsTestCase):
    def setUp(self):
        # type: () -> None
        super(TestCountStats, self).setUp()
        # This tests two things for each of the queries/CountStats: Handling
        # more than 1 realm, and the time bounds (time_start and time_end in
        # the queries).
        self.second_realm = Realm.objects.create(
            string_id='second-realm', name='Second Realm',
            domain='second.analytics', date_created=self.TIME_ZERO-2*self.DAY)
        for minutes_ago in [0, 1, 61, 60*24+1]:
            creation_time = self.TIME_ZERO - minutes_ago*self.MINUTE
            user = self.create_user(email='user-%s@second.analytics' % (minutes_ago,),
                                    realm=self.second_realm, date_joined=creation_time)
            recipient = self.create_stream_with_recipient(
                name='stream %s' % (minutes_ago,), realm=self.second_realm,
                date_created=creation_time)[1]
            self.create_message(user, recipient, pub_date=creation_time)
        self.hourly_user = UserProfile.objects.get(email='user-1@second.analytics')
        self.daily_user = UserProfile.objects.get(email='user-61@second.analytics')

        # This realm should not show up in the *Count tables for any of the
        # messages_* CountStats
        self.no_message_realm = Realm.objects.create(
            string_id='no-message-realm', name='No Message Realm',
            domain='no.message', date_created=self.TIME_ZERO-2*self.DAY)
        self.create_user(realm=self.no_message_realm)
        self.create_stream_with_recipient(realm=self.no_message_realm)
        # This huddle should not show up anywhere
        self.create_huddle_with_recipient()

    def test_active_users_by_is_bot(self):
        # type: () -> None
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
        self.assertTableState(InstallationCount, ['value', 'subgroup'], [[2, 'true'], [5, 'false']])
        self.assertTableState(UserCount, [], [])
        self.assertTableState(StreamCount, [], [])

    def test_messages_sent_by_is_bot(self):
        # type: () -> None
        stat = COUNT_STATS['messages_sent:is_bot:hour']
        self.current_property = stat.property

        bot = self.create_user(is_bot=True)
        human1 = self.create_user()
        human2 = self.create_user()
        recipient_human1 = Recipient.objects.create(type_id=human1.id, type=Recipient.PERSONAL)

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

    def test_messages_sent_by_message_type(self):
        # type: () -> None
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
                               [2, 'private_message', user1],
                               [2, 'private_message', user2],
                               [1, 'private_message', user3],
                               [1, 'public_stream', self.hourly_user],
                               [1, 'public_stream', self.daily_user]])
        self.assertTableState(RealmCount, ['value', 'subgroup', 'realm'],
                              [[3, 'private_stream'], [3, 'public_stream'], [5, 'private_message'],
                               [2, 'public_stream', self.second_realm]])
        self.assertTableState(InstallationCount, ['value', 'subgroup'],
                              [[3, 'private_stream'], [5, 'public_stream'], [5, 'private_message']])
        self.assertTableState(StreamCount, [], [])

    def test_messages_sent_to_recipients_with_same_id(self):
        # type: () -> None
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

        self.assertCountEquals(UserCount, 2, subgroup='private_message')
        self.assertCountEquals(UserCount, 1, subgroup='public_stream')

    def test_messages_sent_by_client(self):
        # type: () -> None
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
        website_client_id = str(get_client('website').id) # default for self.create_message
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

    def test_messages_sent_to_stream_by_is_bot(self):
        # type: () -> None
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

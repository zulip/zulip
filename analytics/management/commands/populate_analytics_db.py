
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Text, Type, Union

from django.core.management.base import BaseCommand
from django.utils.timezone import now as timezone_now

from analytics.lib.counts import COUNT_STATS, \
    CountStat, do_drop_all_analytics_tables
from analytics.lib.fixtures import generate_time_series_data
from analytics.lib.time_utils import time_range
from analytics.models import BaseCount, FillState, RealmCount, UserCount, StreamCount
from zerver.lib.timestamp import floor_to_day
from zerver.models import Realm, UserProfile, Stream, Message, Client, \
    RealmAuditLog, Recipient

class Command(BaseCommand):
    help = """Populates analytics tables with randomly generated data."""

    DAYS_OF_DATA = 100
    random_seed = 26

    def create_user(self, email: Text,
                    full_name: Text,
                    is_staff: bool,
                    date_joined: datetime,
                    realm: Realm) -> UserProfile:
        user = UserProfile.objects.create(
            email=email, full_name=full_name, is_staff=is_staff,
            realm=realm, short_name=full_name, pointer=-1, last_pointer_updater='none',
            api_key='42', date_joined=date_joined)
        RealmAuditLog.objects.create(
            realm=realm, modified_user=user, event_type='user_created',
            event_time=user.date_joined)
        return user

    def generate_fixture_data(self, stat: CountStat, business_hours_base: float,
                              non_business_hours_base: float, growth: float,
                              autocorrelation: float, spikiness: float,
                              holiday_rate: float=0, partial_sum: bool=False) -> List[int]:
        self.random_seed += 1
        return generate_time_series_data(
            days=self.DAYS_OF_DATA, business_hours_base=business_hours_base,
            non_business_hours_base=non_business_hours_base, growth=growth,
            autocorrelation=autocorrelation, spikiness=spikiness, holiday_rate=holiday_rate,
            frequency=stat.frequency, partial_sum=partial_sum, random_seed=self.random_seed)

    def handle(self, *args: Any, **options: Any) -> None:
        do_drop_all_analytics_tables()
        # I believe this also deletes any objects with this realm as a foreign key
        Realm.objects.filter(string_id='analytics').delete()

        installation_time = timezone_now() - timedelta(days=self.DAYS_OF_DATA)
        last_end_time = floor_to_day(timezone_now())
        realm = Realm.objects.create(
            string_id='analytics', name='Analytics', date_created=installation_time)
        shylock = self.create_user('shylock@analytics.ds', 'Shylock', True, installation_time, realm)
        stream = Stream.objects.create(
            name='all', realm=realm, date_created=installation_time)
        Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)

        def insert_fixture_data(stat: CountStat,
                                fixture_data: Mapping[Optional[str], List[int]],
                                table: Type[BaseCount]) -> None:
            end_times = time_range(last_end_time, last_end_time, stat.frequency,
                                   len(list(fixture_data.values())[0]))
            if table == RealmCount:
                id_args = {'realm': realm}
            if table == UserCount:
                id_args = {'realm': realm, 'user': shylock}
            if table == StreamCount:
                id_args = {'stream': stream, 'realm': realm}

            for subgroup, values in fixture_data.items():
                table.objects.bulk_create([
                    table(property=stat.property, subgroup=subgroup, end_time=end_time,
                          value=value, **id_args)
                    for end_time, value in zip(end_times, values) if value != 0])

        stat = COUNT_STATS['realm_active_humans::day']
        realm_data = {
            None: self.generate_fixture_data(stat, .1, .03, 3, .5, 3, partial_sum=True),
        }  # type: Mapping[Optional[str], List[int]]
        insert_fixture_data(stat, realm_data, RealmCount)
        FillState.objects.create(property=stat.property, end_time=last_end_time,
                                 state=FillState.DONE)

        stat = COUNT_STATS['messages_sent:is_bot:hour']
        user_data = {'false': self.generate_fixture_data(
            stat, 2, 1, 1.5, .6, 8, holiday_rate=.1)}  # type: Mapping[Optional[str], List[int]]
        insert_fixture_data(stat, user_data, UserCount)
        realm_data = {'false': self.generate_fixture_data(stat, 35, 15, 6, .6, 4),
                      'true': self.generate_fixture_data(stat, 15, 15, 3, .4, 2)}
        insert_fixture_data(stat, realm_data, RealmCount)
        FillState.objects.create(property=stat.property, end_time=last_end_time,
                                 state=FillState.DONE)

        stat = COUNT_STATS['messages_sent:message_type:day']
        user_data = {
            'public_stream': self.generate_fixture_data(stat, 1.5, 1, 3, .6, 8),
            'private_message': self.generate_fixture_data(stat, .5, .3, 1, .6, 8),
            'huddle_message': self.generate_fixture_data(stat, .2, .2, 2, .6, 8)}
        insert_fixture_data(stat, user_data, UserCount)
        realm_data = {
            'public_stream': self.generate_fixture_data(stat, 30, 8, 5, .6, 4),
            'private_stream': self.generate_fixture_data(stat, 7, 7, 5, .6, 4),
            'private_message': self.generate_fixture_data(stat, 13, 5, 5, .6, 4),
            'huddle_message': self.generate_fixture_data(stat, 6, 3, 3, .6, 4)}
        insert_fixture_data(stat, realm_data, RealmCount)
        FillState.objects.create(property=stat.property, end_time=last_end_time,
                                 state=FillState.DONE)

        website, created = Client.objects.get_or_create(name='website')
        old_desktop, created = Client.objects.get_or_create(name='desktop app Linux 0.3.7')
        android, created = Client.objects.get_or_create(name='ZulipAndroid')
        iOS, created = Client.objects.get_or_create(name='ZulipiOS')
        react_native, created = Client.objects.get_or_create(name='ZulipMobile')
        API, created = Client.objects.get_or_create(name='API: Python')
        zephyr_mirror, created = Client.objects.get_or_create(name='zephyr_mirror')
        unused, created = Client.objects.get_or_create(name='unused')
        long_webhook, created = Client.objects.get_or_create(name='ZulipLooooooooooongNameWebhook')

        stat = COUNT_STATS['messages_sent:client:day']
        user_data = {
            website.id: self.generate_fixture_data(stat, 2, 1, 1.5, .6, 8),
            zephyr_mirror.id: self.generate_fixture_data(stat, 0, .3, 1.5, .6, 8)}
        insert_fixture_data(stat, user_data, UserCount)
        realm_data = {
            website.id: self.generate_fixture_data(stat, 30, 20, 5, .6, 3),
            old_desktop.id: self.generate_fixture_data(stat, 5, 3, 8, .6, 3),
            android.id: self.generate_fixture_data(stat, 5, 5, 2, .6, 3),
            iOS.id: self.generate_fixture_data(stat, 5, 5, 2, .6, 3),
            react_native.id: self.generate_fixture_data(stat, 5, 5, 10, .6, 3),
            API.id: self.generate_fixture_data(stat, 5, 5, 5, .6, 3),
            zephyr_mirror.id: self.generate_fixture_data(stat, 1, 1, 3, .6, 3),
            unused.id: self.generate_fixture_data(stat, 0, 0, 0, 0, 0),
            long_webhook.id: self.generate_fixture_data(stat, 5, 5, 2, .6, 3)}
        insert_fixture_data(stat, realm_data, RealmCount)
        FillState.objects.create(property=stat.property, end_time=last_end_time,
                                 state=FillState.DONE)

        stat = COUNT_STATS['messages_in_stream:is_bot:day']
        realm_data = {'false': self.generate_fixture_data(stat, 30, 5, 6, .6, 4),
                      'true': self.generate_fixture_data(stat, 20, 2, 3, .2, 3)}
        insert_fixture_data(stat, realm_data, RealmCount)
        stream_data = {'false': self.generate_fixture_data(stat, 10, 7, 5, .6, 4),
                       'true': self.generate_fixture_data(stat, 5, 3, 2, .4, 2)}  # type: Mapping[Optional[str], List[int]]
        insert_fixture_data(stat, stream_data, StreamCount)
        FillState.objects.create(property=stat.property, end_time=last_end_time,
                                 state=FillState.DONE)

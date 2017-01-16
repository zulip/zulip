from __future__ import absolute_import, print_function

from argparse import ArgumentParser

from django.core.management.base import BaseCommand
from django.utils import timezone

from analytics.models import BaseCount, InstallationCount, RealmCount, \
    UserCount, StreamCount
from analytics.lib.counts import COUNT_STATS, CountStat, do_drop_all_analytics_tables
from analytics.lib.fixtures import generate_time_series_data
from analytics.lib.time_utils import time_range
from zerver.lib.timestamp import floor_to_day
from zerver.models import Realm, UserProfile, Stream, Message

from datetime import datetime, timedelta

from six.moves import zip
from typing import Any, List, Optional, Text, Type, Union

class Command(BaseCommand):
    help = """Populates analytics tables with randomly generated data."""

    DAYS_OF_DATA = 100

    def create_user(self, email, full_name, is_staff, date_joined, realm):
        # type: (Text, Text, Text, bool, datetime, Realm) -> UserProfile
        return UserProfile.objects.create(
            email=email, full_name=full_name, is_staff=is_staff,
            realm=realm, short_name=full_name, pointer=-1, last_pointer_updater='none',
            api_key='42', date_joined=date_joined)

    def generate_fixture_data(self, stat, business_hours_base, non_business_hours_base,
                              growth, autocorrelation, spikiness, holiday_rate=0):
        # type: (CountStat, float, float, float, float, float, float) -> List[int]
        return generate_time_series_data(
            days=self.DAYS_OF_DATA, business_hours_base=business_hours_base,
            non_business_hours_base=non_business_hours_base, growth=growth,
            autocorrelation=autocorrelation, spikiness=spikiness, holiday_rate=holiday_rate,
            frequency=stat.frequency, is_gauge=(stat.interval == CountStat.GAUGE))

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        do_drop_all_analytics_tables()
        # I believe this also deletes any objects with this realm as a foreign key
        Realm.objects.filter(string_id='analytics').delete()

        installation_time = timezone.now() - timedelta(days=self.DAYS_OF_DATA)
        last_end_time = floor_to_day(timezone.now())
        realm = Realm.objects.create(
            string_id='analytics', name='Analytics', domain='analytics.ds',
            date_created=installation_time)
        shylock = self.create_user('shylock@analytics.ds', 'Shylock', True, installation_time, realm)

        def insert_fixture_data(stat, fixture_data, table):
            # type: (CountStat, Dict[Optional[str], List[int]], Type[BaseCount]) -> None
            end_times = time_range(last_end_time, last_end_time, stat.frequency,
                                   len(list(fixture_data.values())[0]))
            if table == RealmCount:
                id_args = {'realm': realm}
            if table == UserCount:
                id_args = {'realm': realm, 'user': shylock}
            for subgroup, values in fixture_data.items():
                table.objects.bulk_create([
                    table(property=stat.property, subgroup=subgroup, end_time=end_time,
                          interval=stat.interval, value=value, **id_args)
                    for end_time, value in zip(end_times, values) if value != 0])

        stat = COUNT_STATS['active_users:is_bot']
        realm_data = {'false': self.generate_fixture_data(stat, .1, .03, 3, .5, 3),
                      'true': self.generate_fixture_data(stat, .01, 0, 1, 0, 1)}
        insert_fixture_data(stat, realm_data, RealmCount)

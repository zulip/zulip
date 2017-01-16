from __future__ import absolute_import, print_function

from argparse import ArgumentParser

from django.core.management.base import BaseCommand
from django.utils import timezone

from analytics.models import InstallationCount, RealmCount, UserCount, StreamCount
from analytics.lib.counts import COUNT_STATS, CountStat, do_drop_all_analytics_tables
from analytics.lib.fixtures import generate_time_series_data, bulk_create_realmcount
from zerver.lib.timestamp import floor_to_day
from zerver.models import Realm, UserProfile, Stream, Message

from datetime import datetime, timedelta
from typing import Any, Text

class Command(BaseCommand):
    help = """Populates analytics tables with randomly generated data."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('--clear-existing',
                            action='store_true',
                            help="Clear analytics tables before populating. If you run "
                            "this twice with this flag, the main change will be in the timestamps "
                            "of all the created database objects.")

    def create_user(self, email, full_name, is_staff, date_joined, realm):
        # type: (Text, Text, Text, bool, datetime, Realm) -> UserProfile
        return UserProfile.objects.get_or_create(
            email=email, full_name=full_name, is_staff=is_staff,
            realm=realm, short_name=full_name, pointer=-1, last_pointer_updater='none',
            api_key='42', defaults={'date_joined': date_joined})[0]

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        if options['clear_existing']:
            do_drop_all_analytics_tables()
            # I believe this also deletes any objects with this realm as a foreign key
            Realm.objects.filter(string_id='analytics').delete()

        installation_time = timezone.now() - timedelta(days=100)
        realm, created = Realm.objects.get_or_create(
            string_id='analytics', name='Analytics', domain='analytics.ds',
            defaults={'date_created': installation_time})
        self.create_user('shylock@analytics.ds', 'Shylock', True, installation_time, realm)

        stat = COUNT_STATS['active_users:is_bot']
        if not RealmCount.objects.filter(property=stat.property).exists():
            last_end_time = floor_to_day(timezone.now())
            human_data = generate_time_series_data(days=100, business_hours_base=30,
                                                   non_business_hours_base=10, growth=5, autocorrelation=.5,
                                                   spikiness=3, frequency=CountStat.DAY)
            bot_data = generate_time_series_data(days=100, business_hours_base=20,
                                                 non_business_hours_base=20, growth=3, frequency=CountStat.DAY)
            bulk_create_realmcount(stat.property, 'false', last_end_time,
                                   stat.frequency, stat.interval, human_data, realm)
            bulk_create_realmcount(stat.property, 'true', last_end_time,
                                   stat.frequency, stat.interval, bot_data, realm)

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Sum

from optparse import make_option

from zerver.models import Realm, UserProfile
from zerver.lib.timestamp import string_to_datetime
from analytics.models import RealmCount
from analytics.views import get_realm_day_counts, dictfetchall
from django.template import loader

from collections import Counter, defaultdict

class Command(BaseCommand):
    help = """Fills RealmCount table.

    Run as a cron job that runs every hour."""

    option_list = BaseCommand.option_list + (
        make_option('-s', '--start_time',
                    dest='start-time', # seems like stylistically, should be start, start_time, or start-time?
                    type='str',
                    help='The interval start time in UTC as a str(datetime).'),
        make_option('-e', '--end-time',
                    dest='end_time',
                    type='str',
                    help='The interval end time in UTC as a str(datetime).'),
        make_option('-g', '--gauge-time',
                    dest='gauge_time',
                    type='str',
                    help='The gauge time in UTC as a str(datetime).'),
    )

    def is_already_inserted(self, property, start_time, interval):
        return len(RealmCount.objects \
                   .filter(start_time = start_time) \
                   .filter(property = property) \
                   .filter(interval = interval)) > 0

    def insert_counts(self, realms, realm_values, property, start_time, interval):
        values = defaultdict(int)
        for realm_value in realm_values:
            values[realm_value['realm']] = realm_value['values']
        RealmCount.objects.bulk_create([RealmCount(domain = realm['domain'],
                                                   realm_id = realm['id'],
                                                   property = property,
                                                   value = values[realm['id']],
                                                   start_time = start_time,
                                                   interval = interval) for realm in realms])

    def process(self, realms, property, value_function, start_time, interval):
        if not self.is_already_inserted(property, start_time, interval):
            values = value_function(start_time, interval)
            self.insert_counts(realms, values, property, start_time, interval)

    ##

    def aggregate_user_to_realm(self, property, start_time, interval):
        pass # UserCount.objects.filter(start_time = start_time).filter(interval = interval) ..

    def aggregate_hour_to_day(self, property, start_time):
        return RealmCount.objects \
                         .filter(start_time__gte = start_time) \
                         .filter(start_time__lt = start_time + timedelta(day = 1)) \
                         .filter(property = property) \
                         .values('realm') \
                         .annotate(value=Sum('value'))

    ##

    def get_active_user_count_by_realm(self, gauge_time, interval):
        pass

    def get_at_risk_count_by_realm(self, gauge_time, interval):
        pass

    def get_user_profile_count_by_realm(self, gauge_time, interval):
        pass

    def get_bot_count_by_realm(self, gauge_time, interval):
        pass

    def get_message_counts_by_user(self, start_time, interval):
        pass



    def get_total_users_by_realm(self, gauge_time, interval):
        return UserProfile.objects \
                          .filter(date_joined__lte = gauge_time) \
                          .values('realm') \
                          .annotate(value=Count('realm'))

    def get_active_users_by_realm(self, start_time, interval):
        pass

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None

        # options: backfill or not, start_time, end_time, gauge_time
        # check that at least one of the options is set

        # get list of realms, and realm->domain mapping, once for everyone
        realms = Realm.objects.filter(date_created__lt = options['end_time']).values('id', 'domain')
        self.process(realms, 'total_users', self.get_total_users_by_realm, options['gauge_time'], 'gauge')

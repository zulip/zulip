from __future__ import absolute_import

from optparse import make_option
from django.core.management.base import BaseCommand
from zerver.models import get_user_profile_by_email, UserActivityInterval, \
    UserProfile
import sys
import datetime
from django.utils.timezone import utc, is_naive

def analyze_activity(options):
    day_start = datetime.datetime.strptime(options["date"], "%Y-%m-%d").replace(tzinfo=utc)
    day_end = day_start + datetime.timedelta(days=1)

    user_profile_query = UserProfile.objects.all()
    if options["realm"]:
        user_profile_query = user_profile_query.filter(realm__domain=options["realm"])

    total_duration = datetime.timedelta(0)
    for user_profile in user_profile_query:
        intervals = UserActivityInterval.objects.filter(user_profile=user_profile,
                                                        end__gte=day_start, start__lte=day_end)
        if len(intervals) == 0:
            continue

        duration = datetime.timedelta(0)
        for interval in intervals:
            start = max(day_start, interval.start)
            end = min(day_end, interval.end)
            duration += end - start

        total_duration += duration
        print user_profile.email, duration

    print "Total Duration: %s" % (total_duration,)
    print "Total Duration in minutes: %s" % (total_duration.total_seconds() / 60.,)
    print "Total Duration amortized to a month: %s" % (total_duration.total_seconds() * 30. / 60.,)

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--realm', action='store'),
        make_option('--date', action='store', default="2013-09-06"),
        )

    def handle(self, *args, **options):
        analyze_activity(options)

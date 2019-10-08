import datetime
from typing import Any, Dict

from django.core.management.base import BaseCommand, CommandParser
from django.utils.timezone import utc

from zerver.lib.statistics import seconds_usage_between
from zerver.models import UserProfile

def analyze_activity(options: Dict[str, Any]) -> None:
    day_start = datetime.datetime.strptime(options["date"], "%Y-%m-%d").replace(tzinfo=utc)
    day_end = day_start + datetime.timedelta(days=options["duration"])

    user_profile_query = UserProfile.objects.all()
    if options["realm"]:
        user_profile_query = user_profile_query.filter(realm__string_id=options["realm"])

    print("Per-user online duration:\n")
    total_duration = datetime.timedelta(0)
    for user_profile in user_profile_query:
        duration = seconds_usage_between(user_profile, day_start, day_end)

        if duration == datetime.timedelta(0):
            continue

        total_duration += duration
        print("%-*s%s" % (37, user_profile.email, duration,))

    print("\nTotal Duration:                      %s" % (total_duration,))
    print("\nTotal Duration in minutes:           %s" % (total_duration.total_seconds() / 60.,))
    print("Total Duration amortized to a month: %s" % (total_duration.total_seconds() * 30. / 60.,))

class Command(BaseCommand):
    help = """Report analytics of user activity on a per-user and realm basis.

This command aggregates user activity data that is collected by each user using Zulip. It attempts
to approximate how much each user has been using Zulip per day, measured by recording each 15 minute
period where some activity has occurred (mouse move or keyboard activity).

It will correctly not count server-initiated reloads in the activity statistics.

The duration flag can be used to control how many days to show usage duration for

Usage: ./manage.py analyze_user_activity [--realm=zulip] [--date=2013-09-10] [--duration=1]

By default, if no date is selected 2013-09-10 is used. If no realm is provided, information
is shown for all realms"""

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--realm', action='store')
        parser.add_argument('--date', action='store', default="2013-09-06")
        parser.add_argument('--duration', action='store', default=1, type=int,
                            help="How many days to show usage information for")

    def handle(self, *args: Any, **options: Any) -> None:
        analyze_activity(options)

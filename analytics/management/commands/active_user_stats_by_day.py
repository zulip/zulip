from __future__ import absolute_import
from __future__ import print_function

import datetime
import pytz

from optparse import make_option
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils.timezone import now as timezone_now
from zerver.lib.statistics import activity_averages_during_day

class Command(BaseCommand):
    help = "Generate statistics on user activity for a given day."

    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        parser.add_argument('--date', default=None, action='store',
                            help="Day to query in format 2013-12-05.  Default is yesterday")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        if options["date"] is None:
            date = timezone_now() - datetime.timedelta(days=1)
        else:
            date = datetime.datetime.strptime(options["date"], "%Y-%m-%d").replace(tzinfo=pytz.utc)
        print("Activity data for", date)
        print(activity_averages_during_day(date))
        print("Please note that the total registered user count is a total for today")

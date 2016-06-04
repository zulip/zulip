from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand
from django.db.models import Count, QuerySet

from zerver.models import UserActivity, UserProfile, Realm, \
    get_realm, get_user_profile_by_email

import datetime

class Command(BaseCommand):
    help = """Report rough client activity globally, for a realm, or for a user

Usage examples:

python manage.py client_activity
python manage.py client_activity zulip.com
python manage.py client_activity jesstess@zulip.com"""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('arg', metavar='<arg>', type=str, nargs='?', default=None,
                            help="realm or user to estimate client activity for")

    def compute_activity(self, user_activity_objects):
        # type: (QuerySet) -> None
        # Report data from the past week.
        #
        # This is a rough report of client activity because we inconsistently
        # register activity from various clients; think of it as telling you
        # approximately how many people from a group have used a particular
        # client recently. For example, this might be useful to get a sense of
        # how popular different versions of a desktop client are.
        #
        # Importantly, this does NOT tell you anything about the relative
        # volumes of requests from clients.
        threshold = datetime.datetime.now() - datetime.timedelta(days=7)
        client_counts = user_activity_objects.filter(
            last_visit__gt=threshold).values("client__name").annotate(
            count=Count('client__name'))

        total = 0
        counts = []
        for client_type in client_counts:
            count = client_type["count"]
            client = client_type["client__name"]
            total += count
            counts.append((count, client))

        counts.sort()

        for count in counts:
            print("%25s %15d" % (count[1], count[0]))
        print("Total:", total)


    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        if options['arg'] is None:
            # Report global activity.
            self.compute_activity(UserActivity.objects.all())
        else:
            arg = options['arg']
            try:
                # Report activity for a user.
                user_profile = get_user_profile_by_email(arg)
                self.compute_activity(UserActivity.objects.filter(
                        user_profile=user_profile))
            except UserProfile.DoesNotExist:
                try:
                    # Report activity for a realm.
                    realm = get_realm(arg)
                    self.compute_activity(UserActivity.objects.filter(
                            user_profile__realm=realm))
                except Realm.DoesNotExist:
                    print("Unknown user or domain %s" % (arg,))
                    exit(1)

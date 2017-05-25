from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand
from django.db.models import Count, QuerySet
from django.utils.timezone import now as timezone_now

from zerver.models import UserActivity, UserProfile, Realm, \
    get_realm, get_user_for_mgmt

import datetime

class Command(BaseCommand):
    help = """Report rough client activity globally, for a realm, or for a user

Usage examples:

./manage.py client_activity
./manage.py client_activity --realm zulip
./manage.py client_activity --email hamlet@zulip.com --realm zulip"""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('--email', metavar='<email_arg>', type=str, default=None,
                            help="email of user to estimate client activity for")
        parser.add_argument('--realm', metavar='<realm_arg>', type=str, default=None,
                            help="realm of user to estimate client activity for")

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
        threshold = timezone_now() - datetime.timedelta(days=7)
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
        if options['email'] is None and options['realm'] is None:
            # Report global activity.
            self.compute_activity(UserActivity.objects.all())
        else:
            if options['email'] is not None and options['realm'] is None:
                email_arg = options['email']
                user_profile = get_user_for_mgmt(email_arg)
                self.compute_activity(UserActivity.objects.filter(
                    user_profile=user_profile))
            if options['realm'] is not None and options['email'] is not None:
                email_arg = options['email']
                realmobj = get_realm(options['realm'])
                user_profile = get_user_for_mgmt(email_arg, realmobj)
                self.compute_activity(UserActivity.objects.filter(
                    user_profile=user_profile))
            else:
                # Report activity for a realm.
                realmobj = get_realm(options['realm'])
                if realmobj.count() <> 0:
                    self.compute_activity(UserActivity.objects.filter(
                        user_profile__realm=realmobj))
                else:
                    print("Unknown realm %s" % (options['realm'],))
                    exit(1)

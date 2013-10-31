from __future__ import absolute_import

from django.core.management.base import BaseCommand
from django.db.models import Count

from zerver.models import UserActivity, UserProfile, Realm, \
    get_realm, get_user_profile_by_email

import datetime

class Command(BaseCommand):
    help = """Report rough client activity globally, for a realm, or for a user

Usage examples:

python manage.py client_activity
python manage.py client_activity zulip.com
python manage.py client_activity jesstess@zulip.com"""

    def compute_activity(self, user_activity_objects):
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
            print "%25s %15d" % (count[1], count[0])
        print "Total:", total


    def handle(self, *args, **options):
        if len(args) == 0:
            # Report global activity.
            self.compute_activity(UserActivity.objects.all())
        elif len(args) == 1:
            try:
                # Report activity for a user.
                user_profile = get_user_profile_by_email(args[0])
                self.compute_activity(UserActivity.objects.filter(
                        user_profile=user_profile))
            except UserProfile.DoesNotExist:
                try:
                    # Report activity for a realm.
                    realm = get_realm(args[0])
                    self.compute_activity(UserActivity.objects.filter(
                            user_profile__realm=realm))
                except Realm.DoesNotExist:
                    print "Unknown user or domain %s" % (args[0],)
                    exit(1)

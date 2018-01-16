import datetime
from argparse import ArgumentParser
from typing import Any

from django.db.models import Count, QuerySet
from django.utils.timezone import now as timezone_now

from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserActivity

class Command(ZulipBaseCommand):
    help = """Report rough client activity globally, for a realm, or for a user

Usage examples:

./manage.py client_activity --target server
./manage.py client_activity --target realm --realm zulip
./manage.py client_activity --target user --user hamlet@zulip.com --realm zulip"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--target', dest='target', required=True, type=str,
                            help="'server' will calculate client activity of the entire server. "
                                 "'realm' will calculate client activity of realm. "
                                 "'user' will calculate client activity of the user.")
        parser.add_argument('--user', dest='user', type=str,
                            help="The email address of the user you want to calculate activity.")
        self.add_realm_args(parser)

    def compute_activity(self, user_activity_objects: QuerySet) -> None:
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

    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        if options["user"] is None:
            if options["target"] == "server" and realm is None:
                # Report global activity.
                self.compute_activity(UserActivity.objects.all())
            elif options["target"] == "realm" and realm is not None:
                self.compute_activity(UserActivity.objects.filter(user_profile__realm=realm))
            else:
                self.print_help("./manage.py", "client_activity")
        elif options["target"] == "user":
            user_profile = self.get_user(options["user"], realm)
            self.compute_activity(UserActivity.objects.filter(user_profile=user_profile))
        else:
            self.print_help("./manage.py", "client_activity")

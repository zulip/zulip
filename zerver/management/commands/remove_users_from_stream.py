from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from django.core.management.base import CommandParser

from zerver.lib.actions import bulk_remove_subscriptions
from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserProfile, get_stream

class Command(ZulipBaseCommand):
    help = """Remove some or all users in a realm from a stream."""

    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        parser.add_argument('-s', '--stream',
                            dest='stream',
                            type=str,
                            help='A stream name.')

        parser.add_argument('-u', '--users',
                            dest='users',
                            type=str,
                            help='A comma-separated list of email addresses.')

        parser.add_argument('-a', '--all-users',
                            dest='all_users',
                            action="store_true",
                            default=False,
                            help='Remove all users in this realm from this stream.')
        self.add_realm_args(parser, True)

    def handle(self, **options):
        # type: (**Any) -> None
        realm = self.get_realm(options)

        if realm is None or options["stream"] is None or \
                (options["users"] is None and not options["all_users"]):
            self.print_help("./manage.py", "remove_users_from_stream")
            exit(1)

        stream_name = options["stream"].strip()
        stream = get_stream(stream_name, realm)

        if options["all_users"]:
            user_profiles = UserProfile.objects.filter(realm=realm)
        else:
            emails = set([email.strip() for email in options["users"].split(",")])
            user_profiles = []
            for email in emails:
                user_profiles.append(self.get_user(email, realm))

        result = bulk_remove_subscriptions(user_profiles, [stream])
        not_subscribed = result[1]
        not_subscribed_users = {tup[0] for tup in not_subscribed}

        for user_profile in user_profiles:
            if user_profile in not_subscribed_users:
                print("%s was not subscribed" % (user_profile.email,))
            else:
                print("Removed %s from %s" % (user_profile.email, stream_name))

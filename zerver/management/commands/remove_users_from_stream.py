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
                            required=True,
                            type=str,
                            help='A stream name.')

        parser.add_argument('-a', '--all-users',
                            dest='all_users',
                            action="store_true",
                            default=False,
                            help='Remove all users in this realm from this stream.')

        self.add_realm_args(parser, True)
        self.add_user_list_args(parser)

    def handle(self, **options):
        # type: (**Any) -> None
        realm = self.get_realm(options)
        user_profiles = self.get_users(options, realm)

        if bool(user_profiles) == options["all_users"]:
            self.print_help("./manage.py", "remove_users_from_stream")
            exit(1)

        stream_name = options["stream"].strip()
        stream = get_stream(stream_name, realm)

        if options["all_users"]:
            user_profiles = UserProfile.objects.filter(realm=realm)

        result = bulk_remove_subscriptions(user_profiles, [stream])
        not_subscribed = result[1]
        not_subscribed_users = {tup[0] for tup in not_subscribed}

        for user_profile in user_profiles:
            if user_profile in not_subscribed_users:
                print("%s was not subscribed" % (user_profile.email,))
            else:
                print("Removed %s from %s" % (user_profile.email, stream_name))

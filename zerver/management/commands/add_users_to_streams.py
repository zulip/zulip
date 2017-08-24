from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from django.core.management.base import CommandParser

from zerver.lib.actions import create_stream_if_needed, bulk_add_subscriptions
from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserProfile

class Command(ZulipBaseCommand):
    help = """Add some or all users in a realm to a set of streams."""

    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        self.add_realm_args(parser, True)
        self.add_user_list_args(parser, all_users_help="Add all users in realm to these streams.")

        parser.add_argument(
            '-s', '--streams',
            dest='streams',
            type=str,
            required=True,
            help='A comma-separated list of stream names.')

    def handle(self, **options):
        # type: (**Any) -> None
        realm = self.get_realm(options)
        user_profiles = self.get_users(options, realm)
        stream_names = set([stream.strip() for stream in options["streams"].split(",")])

        for stream_name in set(stream_names):
            for user_profile in user_profiles:
                stream, _ = create_stream_if_needed(realm, stream_name)
                _ignore, already_subscribed = bulk_add_subscriptions([stream], [user_profile])
                was_there_already = user_profile.id in {tup[0].id for tup in already_subscribed}
                print("%s %s to %s" % (
                    "Already subscribed" if was_there_already else "Subscribed",
                    user_profile.email, stream_name))

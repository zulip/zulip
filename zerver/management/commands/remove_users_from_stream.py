
from typing import Any

from django.core.management.base import CommandParser

from zerver.lib.actions import bulk_remove_subscriptions
from zerver.lib.management import ZulipBaseCommand
from zerver.models import get_stream

class Command(ZulipBaseCommand):
    help = """Remove some or all users in a realm from a stream."""

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('-s', '--stream',
                            dest='stream',
                            required=True,
                            type=str,
                            help='A stream name.')

        self.add_realm_args(parser, True)
        self.add_user_list_args(parser, all_users_help='Remove all users in realm from this stream.')

    def handle(self, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser
        user_profiles = self.get_users(options, realm)
        stream_name = options["stream"].strip()
        stream = get_stream(stream_name, realm)

        result = bulk_remove_subscriptions(user_profiles, [stream])
        not_subscribed = result[1]
        not_subscribed_users = {tup[0] for tup in not_subscribed}

        for user_profile in user_profiles:
            if user_profile in not_subscribed_users:
                print("%s was not subscribed" % (user_profile.email,))
            else:
                print("Removed %s from %s" % (user_profile.email, stream_name))

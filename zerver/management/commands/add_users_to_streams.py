from typing import Any

from django.core.management.base import CommandParser

from zerver.actions.streams import bulk_add_subscriptions
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.streams import ensure_stream


class Command(ZulipBaseCommand):
    help = """Add some or all users in a realm to a set of streams."""

    def add_arguments(self, parser: CommandParser) -> None:
        self.add_realm_args(parser, required=True)
        self.add_user_list_args(parser, all_users_help="Add all users in realm to these streams.")

        parser.add_argument(
            "-s", "--streams", required=True, help="A comma-separated list of stream names."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        user_profiles = self.get_users(options, realm)
        stream_names = {stream.strip() for stream in options["streams"].split(",")}

        for stream_name in stream_names:
            for user_profile in user_profiles:
                stream = ensure_stream(realm, stream_name, acting_user=None)
                _ignore, already_subscribed = bulk_add_subscriptions(
                    realm, [stream], [user_profile], acting_user=None
                )
                was_there_already = user_profile.id in (info.user.id for info in already_subscribed)
                print(
                    "{} {} to {}".format(
                        "Already subscribed" if was_there_already else "Subscribed",
                        user_profile.delivery_email,
                        stream_name,
                    )
                )

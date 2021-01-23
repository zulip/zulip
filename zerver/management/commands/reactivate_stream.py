from typing import Any

from django.core.management.base import CommandParser

from zerver.lib.actions import do_reactivate_stream
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Script to reactivate a deactivated stream."""

    def add_arguments(self, parser: CommandParser) -> None:
        self.add_realm_args(parser, True, "realm in which stream has to be reactivated.")
        parser.add_argument(
            "stream_name", metavar="<stream name>", help="name of the stream to reactivate"
        )
        parser.add_argument(
            "email",
            metavar="<email>",
            help="email of the user to be subscribed to the reactivated stream",
        )

    def handle(self, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser
        user = self.get_user(options["email"], realm)
        stream_name = options["stream_name"]
        stream = self.get_stream(stream_name, realm)

        do_reactivate_stream(stream, user)
        print("Done!")

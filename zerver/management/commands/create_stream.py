from argparse import ArgumentParser
from typing import Any

from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.streams import create_stream_if_needed


class Command(ZulipBaseCommand):
    help = """Create a stream, and subscribe all active users (excluding bots).

This should be used for TESTING only, unless you understand the limitations of
the command."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, required=True, help="realm in which to create the stream")
        parser.add_argument("stream_name", metavar="<stream name>", help="name of stream to create")

    @override
    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        stream_name = options["stream_name"]
        create_stream_if_needed(realm, stream_name, acting_user=None)

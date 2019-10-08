
import sys
from argparse import ArgumentParser
from typing import Any

from zerver.lib.actions import create_stream_if_needed
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """Create a stream, and subscribe all active users (excluding bots).

This should be used for TESTING only, unless you understand the limitations of
the command."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, True, "realm in which to create the stream")
        parser.add_argument('stream_name', metavar='<stream name>', type=str,
                            help='name of stream to create')

    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        stream_name = options['stream_name']
        create_stream_if_needed(realm, stream_name)

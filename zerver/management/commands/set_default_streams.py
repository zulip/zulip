
import sys
from argparse import ArgumentParser
from typing import Any, Dict

from zerver.lib.actions import set_default_streams
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """Set default streams for a realm

Users created under this realm will start out with these streams. This
command is not additive: if you re-run it on a realm with a different
set of default streams, those will be the new complete set of default
streams.

For example:

./manage.py set_default_streams --realm=foo --streams=foo,bar,baz
./manage.py set_default_streams --realm=foo --streams="foo,bar,baz with space"
./manage.py set_default_streams --realm=foo --streams=
"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('-s', '--streams',
                            dest='streams',
                            type=str,
                            help='A comma-separated list of stream names.')
        self.add_realm_args(parser, True)

    def handle(self, **options: str) -> None:
        realm = self.get_realm(options)
        if options["streams"] is None:
            print("Please provide a default set of streams (which can be empty,\
with `--streams=`).", file=sys.stderr)
            exit(1)
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        stream_dict = {
            stream.strip(): {"description": stream.strip(), "invite_only": False}
            for stream in options["streams"].split(",")
        }  # type: Dict[str, Dict[str, Any]]

        set_default_streams(realm, stream_dict)

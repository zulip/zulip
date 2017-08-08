from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from zerver.lib.actions import create_stream_if_needed
from zerver.lib.str_utils import force_text
from zerver.lib.management import ZulipBaseCommand

from argparse import ArgumentParser
import sys

class Command(ZulipBaseCommand):
    help = """Create a stream, and subscribe all active users (excluding bots).

This should be used for TESTING only, unless you understand the limitations of
the command."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        self.add_realm_args(parser, True, "realm in which to create the stream")
        parser.add_argument('stream_name', metavar='<stream name>', type=str,
                            help='name of stream to create')

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = self.get_realm(options)
        encoding = sys.getfilesystemencoding()
        stream_name = options['stream_name']
        create_stream_if_needed(realm, force_text(stream_name, encoding))

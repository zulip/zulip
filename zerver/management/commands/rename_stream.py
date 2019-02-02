from argparse import ArgumentParser
from typing import Any

from zerver.lib.actions import do_rename_stream
from zerver.lib.management import ZulipBaseCommand
from zerver.models import get_stream

class Command(ZulipBaseCommand):
    help = """Change the stream name for a realm."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('old_name', metavar='<old name>', type=str,
                            help='name of stream to be renamed')
        parser.add_argument('new_name', metavar='<new name>', type=str,
                            help='new name to rename the stream to')
        self.add_realm_args(parser, True)

    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser
        old_name = options['old_name']
        new_name = options['new_name']

        stream = get_stream(old_name, realm)
        do_rename_stream(stream, new_name, self.user_profile)

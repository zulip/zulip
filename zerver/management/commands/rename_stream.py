from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser

from zerver.lib.actions import do_rename_stream
from zerver.lib.str_utils import force_text
from zerver.lib.management import ZulipBaseCommand
from zerver.models import get_stream

import sys

class Command(ZulipBaseCommand):
    help = """Change the stream name for a realm."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('old_name', metavar='<old name>', type=str,
                            help='name of stream to be renamed')
        parser.add_argument('new_name', metavar='<new name>', type=str,
                            help='new name to rename the stream to')
        self.add_realm_args(parser, True)

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = self.get_realm(options)
        old_name = options['old_name']
        new_name = options['new_name']
        encoding = sys.getfilesystemencoding()

        stream = get_stream(force_text(old_name, encoding), realm)
        do_rename_stream(stream, force_text(new_name, encoding))

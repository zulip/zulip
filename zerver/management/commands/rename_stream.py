from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand

from zerver.lib.actions import do_rename_stream
from zerver.lib.str_utils import force_text
from zerver.models import Realm, get_realm, get_stream

import sys

class Command(BaseCommand):
    help = """Change the stream name for a realm."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('string_id', metavar='<string_id>', type=str,
                            help="subdomain or string_id to operate on")
        parser.add_argument('old_name', metavar='<old name>', type=str,
                            help='name of stream to be renamed')
        parser.add_argument('new_name', metavar='<new name>', type=str,
                            help='new name to rename the stream to')

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        string_id = options['string_id']
        old_name = options['old_name']
        new_name = options['new_name']
        encoding = sys.getfilesystemencoding()

        realm = get_realm(force_text(string_id, encoding))
        if realm is None:
            print("Unknown subdomain or string_id %s" % (string_id,))
            exit(1)

        stream = get_stream(force_text(old_name, encoding), realm)
        do_rename_stream(stream, force_text(new_name, encoding))

from __future__ import absolute_import
from __future__ import print_function

from six import text_type
from typing import Any

from django.core.management.base import BaseCommand

from zerver.lib.actions import do_create_stream
from zerver.lib.str_utils import force_text
from zerver.models import Realm, get_realm

from argparse import ArgumentParser
import sys

class Command(BaseCommand):
    help = """Create a stream, and subscribe all active users (excluding bots).

This should be used for TESTING only, unless you understand the limitations of
the command."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('domain', metavar='<domain>', type=str,
                            help='domain in which to create the stream')
        parser.add_argument('stream_name', metavar='<stream name>', type=str,
                            help='name of stream to create')

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        domain = options['domain']
        encoding = sys.getfilesystemencoding()
        stream_name = options['stream_name']

        realm = get_realm(force_text(domain, encoding))
        if realm is None:
            print("Unknown domain %s" % (domain,))
            exit(1)
        else:
            do_create_stream(realm, force_text(stream_name, encoding))

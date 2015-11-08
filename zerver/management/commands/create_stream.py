from __future__ import absolute_import
from __future__ import print_function

from django.core.management.base import BaseCommand

from zerver.lib.actions import do_create_stream
from zerver.models import Realm, get_realm

import sys

class Command(BaseCommand):
    help = """Create a stream, and subscribe all active users (excluding bots).

This should be used for TESTING only, unless you understand the limitations of
the command."""

    def add_arguments(self, parser):
        parser.add_argument('domain', metavar='<domain>', type=str,
                            help='domain in which to create the stream')
        parser.add_argument('stream_name', metavar='<stream name>', type=str,
                            help='name of stream to create')

    def handle(self, *args, **options):
        domain = options['domain']
        stream_name = options['stream_name']
        encoding = sys.getfilesystemencoding()

        try:
            realm = get_realm(domain)
        except Realm.DoesNotExist:
            print("Unknown domain %s" % (domain,))
            exit(1)

        do_create_stream(realm, stream_name.decode(encoding))

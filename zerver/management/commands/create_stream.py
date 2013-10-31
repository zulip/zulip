from __future__ import absolute_import

from django.core.management.base import BaseCommand

from zerver.lib.actions import do_create_stream
from zerver.models import Realm, get_realm

import sys

class Command(BaseCommand):
    help = """Create a stream, and subscribe all active users (excluding bots).

This should be used for TESTING only, unless you understand the limitations of
the command.

Usage: python manage.py create_stream <domain> <stream name>"""

    def handle(self, *args, **options):
        if len(args) != 2:
            print "Please provide a domain and the stream name."
            exit(1)

        domain, stream_name = args
        encoding = sys.getfilesystemencoding()

        try:
            realm = get_realm(domain)
        except Realm.DoesNotExist:
            print "Unknown domain %s" % (domain,)
            exit(1)

        do_create_stream(realm, stream_name.decode(encoding))

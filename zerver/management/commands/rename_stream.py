from __future__ import absolute_import

from django.core.management.base import BaseCommand

from zerver.lib.actions import do_rename_stream
from zerver.models import Realm, get_realm

import sys

class Command(BaseCommand):
    help = """Change the stream name for a realm.

Usage: python manage.py rename_stream <domain> <old name> <new name>"""

    def handle(self, *args, **options):
        if len(args) != 3:
            print "Please provide a domain and the old and new names."
            exit(1)

        domain, old_name, new_name = args
        encoding = sys.getfilesystemencoding()

        try:
            realm = get_realm(domain)
        except Realm.DoesNotExist:
            print "Unknown domain %s" % (domain,)
            exit(1)

        do_rename_stream(realm, old_name.decode(encoding),
                         new_name.decode(encoding))

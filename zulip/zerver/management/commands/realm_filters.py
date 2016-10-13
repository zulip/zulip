from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from optparse import make_option

from django.core.management.base import BaseCommand
from zerver.models import RealmFilter, all_realm_filters, get_realm
from zerver.lib.actions import do_add_realm_filter, do_remove_realm_filter
import sys

class Command(BaseCommand):
    help = """Create a link filter rule for the specified domain.

NOTE: Regexes must be simple enough that they can be easily translated to JavaScript
      RegExp syntax. In addition to JS-compatible syntax, the following features are available:

      * Named groups will be converted to numbered groups automatically
      * Inline-regex flags will be stripped, and where possible translated to RegExp-wide flags

Example: python manage.py realm_filters --realm=zulip.com --op=add '#(?P<id>[0-9]{2,8})' 'https://trac.humbughq.com/ticket/%(id)s'
Example: python manage.py realm_filters --realm=zulip.com --op=remove '#(?P<id>[0-9]{2,8})'
Example: python manage.py realm_filters --realm=zulip.com --op=show
"""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('-r', '--realm',
                            dest='domain',
                            type=str,
                            required=True,
                            help='The name of the realm to adjust filters for.')
        parser.add_argument('--op',
                            dest='op',
                            type=str,
                            default="show",
                            help='What operation to do (add, show, remove).')
        parser.add_argument('pattern', metavar='<pattern>', type=str, nargs='?', default=None,
                            help="regular expression to match")
        parser.add_argument('url_format_string', metavar='<url pattern>', type=str, nargs='?',
                            help="format string to substitute")

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = get_realm(options["domain"])
        if options["op"] == "show":
            print("%s: %s" % (realm.domain, all_realm_filters().get(realm.domain, [])))
            sys.exit(0)

        pattern = options['pattern']
        if not pattern:
            self.print_help("python manage.py", "realm_filters")
            sys.exit(1)

        if options["op"] == "add":
            url_format_string = options['url_format_string']
            if not url_format_string:
                self.print_help("python manage.py", "realm_filters")
                sys.exit(1)
            do_add_realm_filter(realm, pattern, url_format_string)
            sys.exit(0)
        elif options["op"] == "remove":
            do_remove_realm_filter(realm, pattern)
            sys.exit(0)
        else:
            self.print_help("python manage.py", "realm_filters")
            sys.exit(1)

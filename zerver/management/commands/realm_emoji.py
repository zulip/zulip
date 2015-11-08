from __future__ import absolute_import
from __future__ import print_function

from django.core.management.base import BaseCommand
from zerver.models import Realm, get_realm
from zerver.lib.actions import do_add_realm_emoji, do_remove_realm_emoji
import sys

class Command(BaseCommand):
    help = """Manage emoji for the specified realm

Example: python2.7 manage.py realm_emoji --realm=zulip.com --op=add robotheart  https://humbug-user-avatars.s3.amazonaws.com/95ffa70fe0e7aea3c052ba91b38a28d8779f5705
Example: python2.7 manage.py realm_emoji --realm=zulip.com --op=remove robotheart
Example: python2.7 manage.py realm_emoji --realm=zulip.com --op=show
"""

    def add_arguments(self, parser):
        parser.add_argument('-r', '--realm',
                            dest='domain',
                            type=str,
                            required=True,
                            help='The name of the realm.')
        parser.add_argument('--op',
                            dest='op',
                            type=str,
                            default="show",
                            help='What operation to do (add, show, remove).')
        parser.add_argument('name', metavar='<name>', type=str, nargs='?', default=None,
                            help="name of the emoji")
        parser.add_argument('img_url', metavar='<image url>', type=str, nargs='?',
                            help="URL of image to display for the emoji")

    def handle(self, *args, **options):
        realm = get_realm(options["domain"])
        if options["op"] == "show":
            for name, url in realm.get_emoji().iteritems():
                print(name, url)
            sys.exit(0)

        name = options['name']
        if name is None:
            self.print_help("python2.7 manage.py", "realm_emoji")
            sys.exit(1)

        if options["op"] == "add":
            img_url = options['img_url']
            if img_url is None:
                self.print_help("python2.7 manage.py", "realm_emoji")
                sys.exit(1)
            do_add_realm_emoji(realm, name, img_url)
            sys.exit(0)
        elif options["op"] == "remove":
            do_remove_realm_emoji(realm, name)
            sys.exit(0)
        else:
            self.print_help("python2.7 manage.py", "realm_emoji")
            sys.exit(1)

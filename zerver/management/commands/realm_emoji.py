from __future__ import absolute_import
from optparse import make_option

from django.core.management.base import BaseCommand
from zerver.models import Realm
from zerver.lib.actions import do_add_realm_emoji, do_remove_realm_emoji
import sys

class Command(BaseCommand):
    help = """Manage emoji for the specified realm

Usage: python manage.py realm_emoji foo.com NAME IMG_URL

Example: python manage.py realm_emoji --realm=zulip.com --op=add robotheart  https://humbug-user-avatars.s3.amazonaws.com/95ffa70fe0e7aea3c052ba91b38a28d8779f5705
Example: python manage.py realm_emoji --realm=zulip.com --op=remove robotheart
Example: python manage.py realm_emoji --realm=zulip.com --op=show
"""

    option_list = BaseCommand.option_list + (
        make_option('-r', '--realm',
                    dest='domain',
                    type='str',
                    help='The name of the realm.'),
        make_option('--op',
                    dest='op',
                    type='str',
                    default="show",
                    help='What operation to do (add, show, remove).'),
        )

    def handle(self, *args, **options):
        if "domain" not in options:
            self.print_help("python manage.py", "realm_emoji")
            sys.exit(1)

        realm = Realm.objects.get(domain=options["domain"])
        if options["op"] == "show":
            for name, url in realm.get_emoji().iteritems():
                print name, url
            sys.exit(0)

        if not args:
            self.print_help("python manage.py", "realm_emoji")
            sys.exit(1)

        name = args[0]
        if options["op"] == "add":
            img_url = args[1]
            do_add_realm_emoji(realm, name, img_url)
            sys.exit(0)
        elif options["op"] == "remove":
            do_remove_realm_emoji(realm, name)
            sys.exit(0)
        else:
            self.print_help("python manage.py", "realm_emoji")
            sys.exit(1)

from __future__ import absolute_import
from optparse import make_option

from django.core.management.base import BaseCommand
from zerver.models import Realm, RealmAlias, get_realm
from zerver.lib.actions import realm_aliases
import sys

class Command(BaseCommand):
    help = """Manage aliases for the specified realm

Usage: python manage.py realm_alias --realm=foo.com --op=[add|remove|show] bar.com

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
        if "domain" not in options or options['domain'] is None:
            self.print_help("python manage.py", "realm_alias")
            sys.exit(1)

        realm = Realm.objects.get(domain=options["domain"])
        if options["op"] == "show":
            print "Aliases for %s:" % (realm.domain,)
            for alias in realm_aliases(realm):
                print alias
            sys.exit(0)

        if not args:
            self.print_help("python manage.py", "realm_alias")
            sys.exit(1)

        alias = args[0]
        if options["op"] == "add":
            if get_realm(alias) is not None:
                print "A Realm already exists for this domain, cannot add it as an alias for another realm!"
                sys.exit(1)
            RealmAlias.objects.create(realm=realm, domain=alias)
            sys.exit(0)
        elif options["op"] == "remove":
            RealmAlias.objects.get(realm=realm, domain=alias).delete()
            sys.exit(0)
        else:
            self.print_help("python manage.py", "realm_alias")
            sys.exit(1)

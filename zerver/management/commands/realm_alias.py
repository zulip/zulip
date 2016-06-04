from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand
from zerver.models import Realm, RealmAlias, get_realm
from zerver.lib.actions import realm_aliases
import sys

class Command(BaseCommand):
    help = """Manage aliases for the specified realm"""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
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
        parser.add_argument('alias', metavar='<alias>', type=str, nargs='?',
                            help="alias to add or remove")

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = get_realm(options["domain"])
        if options["op"] == "show":
            print("Aliases for %s:" % (realm.domain,))
            for alias in realm_aliases(realm):
                print(alias)
            sys.exit(0)

        alias = options['alias']
        if options["op"] == "add":
            if get_realm(alias) is not None:
                print("A Realm already exists for this domain, cannot add it as an alias for another realm!")
                sys.exit(1)
            RealmAlias.objects.create(realm=realm, domain=alias)
            sys.exit(0)
        elif options["op"] == "remove":
            RealmAlias.objects.get(realm=realm, domain=alias).delete()
            sys.exit(0)
        else:
            self.print_help("python manage.py", "realm_alias")
            sys.exit(1)

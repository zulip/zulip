from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from django.utils.translation import ugettext as _
from zerver.models import get_realm, can_add_alias, \
    Realm, RealmAlias
from zerver.lib.actions import get_realm_aliases
from zerver.lib.domains import validate_domain
import sys

class Command(BaseCommand):
    help = """Manage aliases for the specified realm"""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('-r', '--realm',
                            dest='string_id',
                            type=str,
                            required=True,
                            help='The subdomain or string_id of the realm.')
        parser.add_argument('--op',
                            dest='op',
                            type=str,
                            default="show",
                            help='What operation to do (add, show, remove).')
        parser.add_argument('--allow-subdomains',
                            dest='allow_subdomains',
                            action="store_true",
                            default=False,
                            help='Whether subdomains are allowed or not.')
        parser.add_argument('alias', metavar='<alias>', type=str, nargs='?',
                            help="alias to add or remove")

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = get_realm(options["string_id"])
        if options["op"] == "show":
            print("Aliases for %s:" % (realm.string_id,))
            for alias in get_realm_aliases(realm):
                if alias["allow_subdomains"]:
                    print(alias["domain"] + " (subdomains allowed)")
                else:
                    print(alias["domain"] + " (subdomains not allowed)")
            sys.exit(0)

        domain = options['alias'].strip().lower()
        try:
            validate_domain(domain)
        except ValidationError as e:
            print(e.messages[0])
            sys.exit(1)
        if options["op"] == "add":
            try:
                if not can_add_alias(domain):
                    print(_("The domain %(domain)s belongs to another organization.") % {'domain': domain})
                    sys.exit(1)
                RealmAlias.objects.create(realm=realm, domain=domain,
                                          allow_subdomains=options["allow_subdomains"])
                sys.exit(0)
            except IntegrityError:
                print(_("The domain %(domain)s is already a part of your organization.") % {'domain': domain})
                sys.exit(1)
        elif options["op"] == "remove":
            try:
                RealmAlias.objects.get(realm=realm, domain=domain).delete()
                sys.exit(0)
            except RealmAlias.DoesNotExist:
                print("No such entry found!")
                sys.exit(1)
        else:
            self.print_help("./manage.py", "realm_alias")
            sys.exit(1)

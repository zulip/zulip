import sys
from argparse import ArgumentParser
from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.db.utils import IntegrityError
from typing_extensions import override

from zerver.lib.domains import validate_domain
from zerver.lib.management import ZulipBaseCommand
from zerver.models import RealmDomain
from zerver.models.realms import get_realm_domains


class Command(ZulipBaseCommand):
    help = """Manage domains for the specified realm"""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--op", default="show", help="What operation to do (add, show, remove)."
        )
        parser.add_argument(
            "--allow-subdomains", action="store_true", help="Whether subdomains are allowed or not."
        )
        parser.add_argument("domain", metavar="<domain>", nargs="?", help="domain to add or remove")
        self.add_realm_args(parser, required=True)

    @override
    def handle(self, *args: Any, **options: str | bool) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser
        if options["op"] == "show":
            print(f"Domains for {realm.string_id}:")
            for realm_domain in get_realm_domains(realm):
                assert isinstance(realm_domain["domain"], str)
                if realm_domain["allow_subdomains"]:
                    print(realm_domain["domain"] + " (subdomains allowed)")
                else:
                    print(realm_domain["domain"] + " (subdomains not allowed)")
            sys.exit(0)

        assert isinstance(options["domain"], str)
        domain = options["domain"].strip().lower()
        try:
            validate_domain(domain)
        except ValidationError as e:
            raise CommandError(e.messages[0])
        if options["op"] == "add":
            assert isinstance(options["allow_subdomains"], bool)
            try:
                RealmDomain.objects.create(
                    realm=realm, domain=domain, allow_subdomains=options["allow_subdomains"]
                )
                sys.exit(0)
            except IntegrityError:
                raise CommandError(f"The domain {domain} is already a part of your organization.")
        elif options["op"] == "remove":
            try:
                RealmDomain.objects.get(realm=realm, domain=domain).delete()
                sys.exit(0)
            except RealmDomain.DoesNotExist:
                raise CommandError("No such entry found!")
        else:
            self.print_help("./manage.py", "realm_domain")
            raise CommandError

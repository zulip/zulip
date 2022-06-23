from argparse import ArgumentParser
from typing import Any

from zerver.actions.create_realm import do_change_realm_subdomain
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Change realm's subdomain."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, required=True)
        parser.add_argument("new_subdomain", metavar="<new subdomain>", help="realm new subdomain")
        parser.add_argument(
            "--skip-redirect",
            action="store_true",
            help="Do not redirect the old name to the new one",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        new_subdomain = options["new_subdomain"]
        do_change_realm_subdomain(
            realm,
            new_subdomain,
            acting_user=None,
            add_deactivated_redirect=not options["skip_redirect"],
        )
        print("Done!")

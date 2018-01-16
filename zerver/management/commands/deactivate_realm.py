
from argparse import ArgumentParser
from typing import Any

from zerver.lib.actions import do_deactivate_realm
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """Script to deactivate a realm."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, True)

    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        if realm.deactivated:
            print("The realm", options["realm_id"], "is already deactivated.")
            exit(0)
        print("Deactivating", options["realm_id"])
        do_deactivate_realm(realm)
        print("Done!")

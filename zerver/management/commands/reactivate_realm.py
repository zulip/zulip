
from argparse import ArgumentParser
from typing import Any

from zerver.lib.actions import do_reactivate_realm
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """Script to reactivate a deactivated realm."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, True)

    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser
        if not realm.deactivated:
            print("Realm", options["realm_id"], "is already active.")
            exit(0)
        print("Reactivating", options["realm_id"])
        do_reactivate_realm(realm)
        print("Done!")

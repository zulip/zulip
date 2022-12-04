from argparse import ArgumentParser
from typing import Any

from zerver.actions.realm_settings import do_scrub_realm
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Script to scrub a deactivated realm."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, required=True)

    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser
        if not realm.deactivated:
            print("Realm", options["realm_id"], "is active. Please deactivate the Realm the first.")
            return
        print("Scrubbing", options["realm_id"])
        do_scrub_realm(realm, acting_user=None)
        print("Done!")

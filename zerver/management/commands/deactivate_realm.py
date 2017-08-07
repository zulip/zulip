from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser

from zerver.lib.actions import do_deactivate_realm
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """Script to deactivate a realm."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        self.add_realm_args(parser, True)

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = self.get_realm(options)
        if realm.deactivated:
            print("The realm", options["realm_id"], "is already deactivated.")
            exit(0)
        print("Deactivating", options["realm_id"])
        do_deactivate_realm(realm)
        print("Done!")

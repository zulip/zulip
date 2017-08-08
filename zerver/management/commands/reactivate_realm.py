from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser

from zerver.lib.actions import do_reactivate_realm
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """Script to reactivate a deactivated realm."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        self.add_realm_args(parser, True)

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = self.get_realm(options)
        if not realm.deactivated:
            print("Realm", options["realm_id"], "is already active.")
            exit(0)
        print("Reactivating", options["realm_id"])
        do_reactivate_realm(realm)
        print("Done!")

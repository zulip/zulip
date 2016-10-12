from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand

import sys

from zerver.lib.actions import do_reactivate_realm
from zerver.models import get_realm

class Command(BaseCommand):
    help = """Script to reactivate a deactivated realm."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('domain', metavar='<domain>', type=str,
                            help='domain of realm to reactivate')

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = get_realm(options["domain"])
        if realm is None:
            print("Could not find realm %s" % (options["domain"],))
            sys.exit(1)
        print("Reactivating", options["domain"])
        do_reactivate_realm(realm)
        print("Done!")

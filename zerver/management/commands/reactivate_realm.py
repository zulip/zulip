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
        parser.add_argument('string_id', metavar='<string_id>', type=str,
                            help='subdomain or string_id of realm to reactivate')

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = get_realm(options["string_id"])
        if realm is None:
            print("Could not find realm %s" % (options["string_id"],))
            sys.exit(1)
        print("Reactivating", options["string_id"])
        do_reactivate_realm(realm)
        print("Done!")

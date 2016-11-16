from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from django.core.management.base import BaseCommand

from argparse import ArgumentParser
import sys

from zerver.lib.actions import do_deactivate_realm
from zerver.models import get_realm_by_string_id

class Command(BaseCommand):
    help = """Script to deactivate a realm."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('string_id', metavar='<string_id>', type=str,
                            help='string_id of realm to deactivate')

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = get_realm_by_string_id(options["string_id"])
        if realm is None:
            print("Could not find realm %s" % (options["string_id"],))
            sys.exit(1)
        print("Deactivating", options["string_id"])
        do_deactivate_realm(realm)
        print("Done!")

from __future__ import absolute_import
from __future__ import print_function

from django.core.management.base import BaseCommand

from zerver.lib.actions import do_deactivate_realm
from zerver.models import get_realm

class Command(BaseCommand):
    help = """One-off script to deactivate our old realms."""

    def add_arguments(self, parser):
        parser.add_argument('domain', metavar='<domain>', type=str,
                            help='domain of realm to deactivate')

    def handle(self, *args, **options):
        print("Deactivating", options["domain"])
        do_deactivate_realm(get_realm(options["domain"]))
        print("Done!")

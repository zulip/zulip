from __future__ import absolute_import

from django.core.management.base import BaseCommand

from zerver.lib.actions import do_deactivate_realm
from zerver.models import get_realm

domains_to_deactivate = """"""

class Command(BaseCommand):
    help = """One-off script to deactivate our old realms."""

    def handle(self, *args, **options):
        for domain in [elt.strip() for elt in domains_to_deactivate.split("\n")]:
            print "Deactivating", domain
            do_deactivate_realm(get_realm(domain))
        print "Done!"

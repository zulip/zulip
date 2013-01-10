from django.core.management.base import BaseCommand
from zephyr.lib.actions import do_create_realm

class Command(BaseCommand):
    help = "Create a realm for the specified domain(s)."

    def handle(self, *args, **options):
        for domain in args:
            realm, created = do_create_realm(domain)
            if created:
                print domain + ": Created."
            else:
                print domain + ": Already exists."


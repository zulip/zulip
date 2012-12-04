from django.core.management.base import BaseCommand
from zephyr.models import Realm, Message, UserProfile, Recipient, create_stream_if_needed, \
        get_client, do_create_realm
from zephyr.views import do_send_message
from django.utils.timezone import now

class Command(BaseCommand):
    help = "Create a realm for the specified domain(s)."

    def handle(self, *args, **options):
        for domain in args:
            realm, created = do_create_realm(domain)
            if created:
                print domain + ": Created."
            else:
                print domain + ": Already exists."


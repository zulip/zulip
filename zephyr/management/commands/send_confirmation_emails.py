from django.core.management.base import BaseCommand

from zephyr.models import get_user_profile_by_email, get_prereg_user_by_email
from zephyr.lib.queue import SimpleQueueClient
from zephyr.lib.actions import do_send_confirmation_email

class Command(BaseCommand):
    """
    Send confirmation e-mails to invited users.

    This command processes events from the `invites` queue.
    """
    def subscribe(self, ch, method, properties, data):
        invitee = get_prereg_user_by_email(data["email"])
        referrer = get_user_profile_by_email(data["referrer_email"])
        do_send_confirmation_email(invitee, referrer)

    def handle(self, *args, **options):
        q = SimpleQueueClient()
        q.register_json_consumer("invites", self.subscribe)
        q.start_consuming()

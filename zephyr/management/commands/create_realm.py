from django.core.management.base import BaseCommand
from zephyr.models import Realm, Message, UserProfile, Recipient, create_stream_if_needed, \
        get_client
from zephyr.views import do_send_message
from django.utils.timezone import now

class Command(BaseCommand):
    help = "Create a realm for the specified domain(s)."

    def handle(self, *args, **options):
        for domain in args:
            realm, created = Realm.objects.get_or_create(domain=domain)
            if not created:
                print domain + ": Realm already exists!"
            else:
                message = Message()
                message.sender = UserProfile.objects.get(user__email="humbug+signups@humbughq.com")
                message.recipient = Recipient.objects.get(type_id=create_stream_if_needed(
                    message.sender.realm, "signups").id, type=Recipient.STREAM)
                message.subject = domain
                message.content = "Signups enabled."
                message.pub_date = now()
                message.sending_client = get_client("Internal")

                do_send_message(message)
                print domain + ": Created."



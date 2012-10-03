from django.core.management.base import NoArgsCommand

from django.contrib.auth.models import User
from zephyr.models import Message, UserProfile, ZephyrClass, Recipient, \
    Subscription, Huddle, Realm, UserMessage
from django.contrib.sessions.models import Session

class Command(NoArgsCommand):
    help = "Clear only tables we change: messages, accounts + sessions"

    def handle_noargs(self, **options):
        for klass in [Message, ZephyrClass, UserProfile, User, Recipient,
                      Realm, Subscription, Huddle, UserMessage]:
            klass.objects.all().delete()
        Session.objects.all().delete()

        self.stdout.write("Successfully cleared the database.\n")

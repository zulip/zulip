from django.core.management.base import NoArgsCommand

from django.contrib.auth.models import User
from zephyr.models import Zephyr, UserProfile, ZephyrClass, Recipient, Subscription
from django.contrib.sessions.models import Session

class Command(NoArgsCommand):
    help = "Clear only tables we change: zephyr + sessions"

    def handle_noargs(self, **options):
        for klass in [Zephyr, ZephyrClass, UserProfile, User, Recipient]:
            klass.objects.all().delete()
        Session.objects.all().delete()

        self.stdout.write("Successfully cleared the database.\n")

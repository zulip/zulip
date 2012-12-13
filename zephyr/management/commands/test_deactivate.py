from optparse import make_option
from django.core.management.base import BaseCommand
from confirmation.models import Confirmation
from zephyr.models import User, MitUser

class Command(BaseCommand):
    help = "Mark one or more users as inactive in the database."

    def handle(self, *args, **options):
        for email in args:
            try:
                user = User.objects.get(email=email)
                if user.is_active:
                    user.is_active = False
                    user.save()
                    print email + ": Deactivated."
                else:
                    print email + ": Already inactive."
            except User.DoesNotExist:
                print email + ": User does not exist in database"

from optparse import make_option
from django.core.management.base import BaseCommand
from confirmation.models import Confirmation
from zephyr.models import get_user_profile_by_email, UserProfile, MitUser

class Command(BaseCommand):
    help = "Mark one or more users as inactive in the database."

    def handle(self, *args, **options):
        for email in args:
            try:
                user_profile = get_user_profile_by_email(email)
                if user_profile.user.is_active:
                    user_profile.user.is_active = False
                    user_profile.user.save()
                    print email + ": Deactivated."
                else:
                    print email + ": Already inactive."
            except UserProfile.DoesNotExist:
                print email + ": User does not exist in database"

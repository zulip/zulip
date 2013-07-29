from __future__ import absolute_import

from django.core.management.base import BaseCommand

from zerver.lib.actions import do_change_user_email
from zerver.models import UserProfile, get_user_profile_by_email

class Command(BaseCommand):
    help = """Change the email address for a user.

Usage: python manage.py change_user_email <old email> <new email>"""

    def handle(self, *args, **options):
        if len(args) != 2:
            print "Please provide both the old and new address."
            exit(1)

        old_email, new_email = args
        try:
            user_profile = get_user_profile_by_email(old_email)
        except UserProfile.DoesNotExist:
            print "Old e-mail doesn't exist in the system."
            exit(1)

        do_change_user_email(user_profile, new_email)

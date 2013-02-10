from django.core.management.base import BaseCommand

from zephyr.lib.actions import do_change_user_email
from zephyr.models import User

class Command(BaseCommand):
    help = """Change the email address for a user.

Usage: python manage.py change_user_email <old email> <new email>"""

    def handle(self, *args, **options):
        if len(args) != 2:
            print "Please provide both the old and new address."
            exit(1)

        old_email, new_email = args
        try:
            user = User.objects.get(email__iexact=old_email)
        except User.DoesNotExist:
            print "Old e-mail doesn't exist in the system."
            exit(1)

        do_change_user_email(user, new_email)

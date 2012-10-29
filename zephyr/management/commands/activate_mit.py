from optparse import make_option
from django.core.management.base import BaseCommand
from confirmation.models import Confirmation
from zephyr.models import User, MitUser

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--resend', '-r', dest='resend', action='store_true',
                    help='Send tokens even if tokens were previously sent for the user.'),)
    help = "Generate an activation email to send to MIT users."

    def handle(self, *args, **options):
        for username in args:
            email = username + "@mit.edu"
            try:
                User.objects.get(email=email)
            except User.DoesNotExist:
                print username + ": User does not exist in database"
                continue
            mit_user, created = MitUser.objects.get_or_create(email=email)
            if not created and not options["resend"]:
                print username + ": User already exists. Use -r to resend."
            else:
                Confirmation.objects.send_confirmation(mit_user, email)
                print username + ": Mailed."


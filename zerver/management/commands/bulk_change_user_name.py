from __future__ import absolute_import

from django.core.management.base import BaseCommand

from zerver.lib.actions import do_change_full_name
from zerver.models import UserProfile, get_user_profile_by_email

class Command(BaseCommand):
    help = """Change the names for many users.

Usage: python manage.py bulk_change_user_name <data file>

Where <data file> contains rows of the form <email>,<desired name>."""

    def handle(self, *args, **options):
        if len(args) != 1:
            print "Please provide a CSV file mapping emails to desired names."
            exit(1)

        data_file = args[0]
        with open(data_file, "r") as f:
            for line in f:
                email, new_name = line.strip().split(",", 1)

                try:
                    user_profile = get_user_profile_by_email(email)
                    old_name = user_profile.full_name
                    print "%s: %s -> %s" % (email, old_name, new_name)
                    do_change_full_name(user_profile, new_name)
                except UserProfile.DoesNotExist:
                    print "* E-mail %s doesn't exist in the system, skipping." % (email,)

from __future__ import absolute_import

from django.core.management.base import BaseCommand

from zerver.lib.actions import send_referral_event
from zerver.models import get_user_profile_by_email

class Command(BaseCommand):
    help = """Grants a user invites and resets the number of invites they've used.

Usage: python manage.py grant_invites <email> <num invites>"""

    def handle(self, *args, **kwargs):
        if len(args) != 2:
            print "Please provide an email address and the number of invites."
            exit(1)

        email = args[0]
        num_invites = int(args[1])

        user_profile = get_user_profile_by_email(email)
        user_profile.invites_granted = num_invites
        user_profile.invites_used = 0

        user_profile.save(update_fields=['invites_granted', 'invites_used'])
        send_referral_event(user_profile)

from __future__ import absolute_import

from django.core.management.base import BaseCommand

from zerver.lib.actions import send_referral_event
from zerver.models import get_user_profile_by_email

class Command(BaseCommand):
    help = """Grants a user invites and resets the number of invites they've used."""

    def add_arguments(self, parser):
        parser.add_argument('email', metavar='<email>', type=str,
                            help="user to grant invites to")
        parser.add_argument('num_invites', metavar='<num invites>', type=int,
                            help="number of invites to grant")

    def handle(self, *args, **options):
        email = options['email']
        num_invites = options['num_invites']

        user_profile = get_user_profile_by_email(email)
        user_profile.invites_granted = num_invites
        user_profile.invites_used = 0

        user_profile.save(update_fields=['invites_granted', 'invites_used'])
        send_referral_event(user_profile)

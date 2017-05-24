from __future__ import absolute_import

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand

from zerver.lib.actions import send_referral_event
from zerver.models import get_user, get_realm

class Command(BaseCommand):
    help = """Grants a user invites and resets the number of invites they've used."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('email', metavar='<email>', type=str,
                            help="user to grant invites to")
        parser.add_argument('num_invites', metavar='<num invites>', type=int,
                            help="number of invites to grant")
        parser.add_argument('realm', metavar='<realm>', type=str, help="realm of user to grant invites to")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        email = options['email']
        num_invites = options['num_invites']

        realm = get_realm(options['realm'])
        user_profile = get_user(email, realm)
        user_profile.invites_granted = num_invites
        user_profile.invites_used = 0

        user_profile.save(update_fields=['invites_granted', 'invites_used'])
        send_referral_event(user_profile)

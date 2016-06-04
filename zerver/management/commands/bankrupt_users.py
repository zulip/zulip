from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand

from zerver.lib.actions import do_update_message_flags
from zerver.models import UserProfile, Message, get_user_profile_by_email

class Command(BaseCommand):
    help = """Bankrupt one or many users."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('emails', metavar='<email>', type=str, nargs='+',
                            help='email address to bankrupt')

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        for email in options['emails']:
            try:
                user_profile = get_user_profile_by_email(email)
            except UserProfile.DoesNotExist:
                print("e-mail %s doesn't exist in the system, skipping" % (email,))
                continue

            do_update_message_flags(user_profile, "add", "read", None, True, None, None)

            messages = Message.objects.filter(
                usermessage__user_profile=user_profile).order_by('-id')[:1]
            if messages:
                old_pointer = user_profile.pointer
                new_pointer = messages[0].id
                user_profile.pointer = new_pointer
                user_profile.save(update_fields=["pointer"])
                print("%s: %d => %d" % (email, old_pointer, new_pointer))
            else:
                print("%s has no messages, can't bankrupt!" % (email,))

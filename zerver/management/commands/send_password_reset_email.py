from __future__ import absolute_import

import logging
from typing import Any, Dict, List, Optional, Text

from argparse import ArgumentParser
from zerver.models import UserProfile
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from django.contrib.auth.tokens import default_token_generator, PasswordResetTokenGenerator

from zerver.lib.send_email import send_email, FromAddress
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """Send email to specified email address."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('--to', metavar='<to>', type=str,
                            help="email of users to send the email")
        parser.add_argument('--target', metavar='<target>', type=str,
                            help="If you pass 'server' will send to everyone on server. "
                                 "If you pass 'realm' will send to everyone on realm."
                                 "Don't forget to specify the realm using -r or --realm flag.")
        self.add_realm_args(parser)

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = self.get_realm(options)
        if options["to"] and options["target"]:
            self.print_help("./manage.py", "send_password_reset_email")
            exit(1)
        if options["to"]:
            users = [self.get_user(options["to"], realm)]
        elif options["target"] == "realm":
            users = UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False,
                                               is_mirror_dummy=False)
        elif options["target"] == "server":
            users = UserProfile.objects.filter(is_active=True, is_bot=False,
                                               is_mirror_dummy=False)
        self.send(users)

    def send(self, users, subject_template_name='', email_template_name='',
             use_https=True, token_generator=default_token_generator,
             from_email=None, html_email_template_name=None):
        # type: (List[UserProfile], str, str, bool, PasswordResetTokenGenerator, Optional[Text], Optional[str]) -> None
        """Sends one-use only links for resetting password to target users

        """
        for user_profile in users:
            context = {
                'email': user_profile.email,
                'domain': user_profile.realm.host,
                'site_name': "zulipo",
                'uid': urlsafe_base64_encode(force_bytes(user_profile.pk)),
                'user': user_profile,
                'token': token_generator.make_token(user_profile),
                'protocol': 'https' if use_https else 'http',
            }

            logging.warning("Sending %s email to %s" % (email_template_name, user_profile.email,))
            send_email('zerver/emails/password_reset', to_user_id=user_profile.id,
                       from_name="Zulip Account Security", from_address=FromAddress.NOREPLY,
                       context=context)

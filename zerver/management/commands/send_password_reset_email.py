
import logging
from argparse import ArgumentParser
from typing import Any, Dict, List, Optional, Text

from django.contrib.auth.tokens import PasswordResetTokenGenerator, \
    default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from zerver.lib.management import CommandError, ZulipBaseCommand
from zerver.lib.send_email import FromAddress, send_email
from zerver.models import UserProfile

class Command(ZulipBaseCommand):
    help = """Send email to specified email address."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--entire-server', action="store_true", default=False,
                            help="Send to every user on the server. ")
        self.add_user_list_args(parser,
                                help="Email addresses of user(s) to send password reset emails to.",
                                all_users_help="Send to every user on the realm.")
        self.add_realm_args(parser)

    def handle(self, *args: Any, **options: str) -> None:
        if options["entire_server"]:
            users = UserProfile.objects.filter(is_active=True, is_bot=False,
                                               is_mirror_dummy=False)
        else:
            realm = self.get_realm(options)
            try:
                users = self.get_users(options, realm)
            except CommandError as error:
                if str(error) == "You have to pass either -u/--users or -a/--all-users.":
                    raise CommandError("You have to pass -u/--users or -a/--all-users or --entire-server.")
                raise error

        self.send(users)

    def send(self, users: List[UserProfile], subject_template_name: str='',
             email_template_name: str='', use_https: bool=True,
             token_generator: PasswordResetTokenGenerator=default_token_generator,
             from_email: Optional[Text]=None, html_email_template_name: Optional[str]=None) -> None:
        """Sends one-use only links for resetting password to target users

        """
        for user_profile in users:
            context = {
                'email': user_profile.email,
                'domain': user_profile.realm.host,
                'site_name': "zulipo",
                'uid': urlsafe_base64_encode(force_bytes(user_profile.id)),
                'user': user_profile,
                'token': token_generator.make_token(user_profile),
                'protocol': 'https' if use_https else 'http',
            }

            logging.warning("Sending %s email to %s" % (email_template_name, user_profile.email,))
            send_email('zerver/emails/password_reset', to_user_id=user_profile.id,
                       from_name="Zulip Account Security", from_address=FromAddress.NOREPLY,
                       context=context)

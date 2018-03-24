
import argparse
import sys
from typing import Any

from django.core import validators
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.db.utils import IntegrityError

from zerver.lib.actions import do_create_user, notify_new_user
from zerver.lib.initial_password import initial_password
from zerver.lib.management import ZulipBaseCommand
from zerver.models import email_to_username

class Command(ZulipBaseCommand):
    help = """Create the specified user with a default initial password.

A user MUST have ALREADY accepted the Terms of Service before creating their
account this way.

Omit both <email> and <full name> for interactive user creation.
"""

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument('--this-user-has-accepted-the-tos',
                            dest='tos',
                            action="store_true",
                            default=False,
                            help='Acknowledgement that the user has already accepted the ToS.')
        parser.add_argument('--password',
                            dest='password',
                            type=str,
                            default='',
                            help='password of new user. For development only.'
                                 'Note that we recommend against setting '
                                 'passwords this way, since they can be snooped by any user account '
                                 'on the server via `ps -ef` or by any superuser with'
                                 'read access to the user\'s bash history.')
        parser.add_argument('--password-file',
                            dest='password_file',
                            type=str,
                            default='',
                            help='The file containing the password of the new user.')
        parser.add_argument('email', metavar='<email>', type=str, nargs='?', default=argparse.SUPPRESS,
                            help='email address of new user')
        parser.add_argument('full_name', metavar='<full name>', type=str, nargs='?',
                            default=argparse.SUPPRESS,
                            help='full name of new user')
        self.add_realm_args(parser, True, "The name of the existing realm to which to add the user.")

    def handle(self, *args: Any, **options: Any) -> None:
        if not options["tos"]:
            raise CommandError("""You must confirm that this user has accepted the
Terms of Service by passing --this-user-has-accepted-the-tos.""")
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        try:
            email = options['email']
            full_name = options['full_name']
            try:
                validators.validate_email(email)
            except ValidationError:
                raise CommandError("Invalid email address.")
        except KeyError:
            if 'email' in options or 'full_name' in options:
                raise CommandError("""Either specify an email and full name as two
parameters, or specify no parameters for interactive user creation.""")
            else:
                while True:
                    email = input("Email: ")
                    try:
                        validators.validate_email(email)
                        break
                    except ValidationError:
                        print("Invalid email address.", file=sys.stderr)
                full_name = input("Full name: ")

        try:
            if 'password' in options:
                pw = options['password']
            if 'password_file' in options:
                pw = open(options['password_file'], 'r').read()
            else:
                user_initial_password = initial_password(email)
                if user_initial_password is None:
                    raise CommandError("Password is unusable.")
                pw = user_initial_password.encode()
            notify_new_user(do_create_user(email, pw,
                                           realm, full_name, email_to_username(email)),
                            internal=True)
        except IntegrityError:
            raise CommandError("User already exists.")

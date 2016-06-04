from __future__ import absolute_import
from __future__ import print_function

from typing import Any

import sys
import argparse

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.core import validators

from zerver.models import Realm, get_realm, email_to_username
from zerver.lib.actions import do_create_user
from zerver.lib.actions import notify_new_user
from zerver.lib.initial_password import initial_password
from six.moves import input

class Command(BaseCommand):
    help = """Create the specified user with a default initial password.

A user MUST have ALREADY accepted the Terms of Service before creating their
account this way.

Omit both <email> and <full name> for interactive user creation.
"""

    def add_arguments(self, parser):
        # type: (argparse.ArgumentParser) -> None
        parser.add_argument('--this-user-has-accepted-the-tos',
                            dest='tos',
                            action="store_true",
                            default=False,
                            help='Acknowledgement that the user has already accepted the ToS.')
        parser.add_argument('--domain',
                            dest='domain',
                            type=str,
                            help='The name of the existing realm to which to add the user.')
        parser.add_argument('email', metavar='<email>', type=str, nargs='?', default=argparse.SUPPRESS,
                            help='email address of new user')
        parser.add_argument('full_name', metavar='<full name>', type=str, nargs='?', default=argparse.SUPPRESS,
                            help='full name of new user')

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        if not options["tos"]:
            raise CommandError("""You must confirm that this user has accepted the
Terms of Service by passing --this-user-has-accepted-the-tos.""")

        if not options["domain"]:
            raise CommandError("""Please specify a realm by passing --domain.""")

        try:
            realm = get_realm(options["domain"])
        except Realm.DoesNotExist:
            raise CommandError("Realm does not exist.")

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
            notify_new_user(do_create_user(email, initial_password(email),
                realm, full_name, email_to_username(email)),
                internal=True)
        except IntegrityError:
            raise CommandError("User already exists.")
